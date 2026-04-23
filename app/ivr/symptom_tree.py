"""DTMF symptom tree for IVR Flow C (wellness check).

Exact state dict from Tech Spec §7.5. On dizziness branch: routes to DDISubAgent
and sends Priya an immediate Telegram alert.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import asyncpg

from app.config import settings

log = logging.getLogger(__name__)

SYMPTOM_TREE: dict[str, dict[str, Any]] = {
    "root": {
        "prompt": "wellness_check_greeting",
        "options": {
            "1": {"outcome": "fine", "tts": "wellness_fine_ack"},
            "2": {"next": "symptom_category"},
            "3": {"outcome": "connect_doctor", "tts": "connecting_doctor"},
        },
    },
    "symptom_category": {
        "prompt": "symptom_tree_prompt",
        "options": {
            "1": {"outcome": "headache"},
            "2": {"outcome": "stomach_pain"},
            "3": {"outcome": "dizziness"},
            "4": {"next": "other_symptom_voice"},
        },
    },
}

_OUTCOME_LABELS = {
    "fine": "reported_well",
    "headache": "headache",
    "stomach_pain": "stomach_pain",
    "dizziness": "dizziness",
    "connect_doctor": "requested_doctor",
    "other_symptom_voice": "other",
}

HIGH_PRIORITY_OUTCOMES = {"dizziness", "connect_doctor"}


async def handle_dtmf(
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    digit: str,
    current_node: str = "root",
) -> str:
    """Process a DTMF keypress in the symptom tree.

    Returns ExoML XML to send back to Exotel.
    """
    node = SYMPTOM_TREE.get(current_node, SYMPTOM_TREE["root"])
    branch = node["options"].get(digit)

    if not branch:
        return _exoml_replay(current_node, call_id, senior_id)

    if "outcome" in branch:
        outcome = branch["outcome"]
        await _persist_symptom(call_id, senior_id, outcome, digit)
        if outcome in HIGH_PRIORITY_OUTCOMES:
            await _alert_guardian(senior_id, outcome)
        tts_key = branch.get("tts", "generic_ack")
        return _exoml_play_hangup(tts_key, call_id=str(call_id))

    if "next" in branch:
        await _update_call_node(call_id, branch["next"])
        return _exoml_gather_next(branch["next"], call_id, senior_id)

    return _exoml_replay(current_node, call_id, senior_id)


def _exoml_play_hangup(tts_key: str, *, call_id: str) -> str:
    from app.ivr.tts import get_tts_url

    text_map = {
        "wellness_fine_ack": "Good to hear you are well. Take care!",
        "connecting_doctor": "We are connecting you to your care team. Please stay on the line.",
        "generic_ack": "Your response has been recorded. Thank you!",
    }
    text = text_map.get(tts_key, "Thank you!")
    url = get_tts_url(text, "en", call_id=call_id)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{url}</Play>
  <Hangup/>
</Response>"""


def _exoml_replay(node_key: str, call_id: uuid.UUID, senior_id: uuid.UUID) -> str:
    from app.ivr.scripts.templates import render_flow_c, render_flow_c_symptom

    if node_key == "symptom_category":
        return render_flow_c_symptom(str(call_id), "en", settings.app_base_url)
    return render_flow_c(str(call_id), "en", settings.app_base_url)


def _exoml_gather_next(next_node: str, call_id: uuid.UUID, senior_id: uuid.UUID) -> str:
    from app.ivr.scripts.templates import render_flow_c_symptom

    return render_flow_c_symptom(str(call_id), "en", settings.app_base_url)


async def _persist_symptom(
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    outcome: str,
    digit: str,
) -> None:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute(
            """UPDATE ivr_call_log
               SET dtmf_responses = COALESCE(dtmf_responses, '{}')::jsonb || $2::jsonb,
                   status='resolved'
               WHERE id=$1""",
            call_id,
            f'{{"digit":"{digit}","outcome":"{outcome}"}}',
        )
        if outcome != "fine":
            symptom_label = _OUTCOME_LABELS.get(outcome, outcome)
            await conn.execute(
                """INSERT INTO telegram_inbound
                   (senior_id, message_type, source, parsed_symptom)
                   VALUES ($1, 'ivr_dtmf', 'ivr', $2)
                   ON CONFLICT DO NOTHING""",
                senior_id,
                symptom_label,
            )
    finally:
        await conn.close()


async def _update_call_node(call_id: uuid.UUID, next_node: str) -> None:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute(
            "UPDATE ivr_call_log SET transcript=$2 WHERE id=$1",
            call_id,
            f"node:{next_node}",
        )
    finally:
        await conn.close()


async def _alert_guardian(senior_id: uuid.UUID, outcome: str) -> None:
    """Send immediate Telegram alert to guardian for high-priority symptom."""
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        row = await conn.fetchrow(
            """SELECT u.full_name, c.guardian_id FROM app_user u
               JOIN care_relationship c ON c.senior_id = u.id
               WHERE u.id=$1 LIMIT 1""",
            senior_id,
        )
        if not row:
            return

        guardian_row = await conn.fetchrow(
            "SELECT telegram_chat_id FROM app_user WHERE id=$1",
            uuid.UUID(str(row["guardian_id"])),
        )
        if not guardian_row or not guardian_row["telegram_chat_id"]:
            return

        chat_id = int(guardian_row["telegram_chat_id"])
        senior_name = str(row["full_name"])

        message = (
            f"🚨 {senior_name} reported *{outcome}* during the IVR wellness check. "
            "Please follow up soon."
        )

        import asyncio

        import httpx

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: httpx.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10,
            ),
        )
        log.info("ivr_symptom_alert senior=%s outcome=%s guardian=%d", senior_id, outcome, chat_id)
    except Exception as exc:
        log.warning("ivr_alert_failed senior=%s err=%s", senior_id, exc)
    finally:
        await conn.close()
