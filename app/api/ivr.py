"""IVR webhook handlers — Exotel and Twilio call events, DTMF, status transitions.

HMAC-SHA256 signature verification on every Exotel webhook.
Exotel posts application/x-www-form-urlencoded.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.config import settings
from app.ivr.scripts.templates import SCRIPT_RENDERERS
from app.ivr.state_machine import transition

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ivr", tags=["ivr"])


def _verify_exotel_hmac(body: bytes, signature: str) -> bool:
    """HMAC-SHA256 with the pre-shared webhook secret."""
    if not settings.exotel_webhook_secret or settings.exotel_webhook_secret.startswith("change-me"):
        return True  # skip in dev when secret not configured
    expected = hmac.new(
        settings.exotel_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.get("/exoml/{script_id}")
async def serve_exoml(script_id: str, call_id: str = "") -> Response:
    """Serve ExoML XML for a given script. Exotel fetches this on call answer."""
    renderer = SCRIPT_RENDERERS.get(script_id)
    if not renderer:
        raise HTTPException(status_code=404, detail=f"Unknown script: {script_id}")

    xml = renderer(call_id, webhook_base=settings.app_base_url)
    return Response(content=xml, media_type="application/xml")


@router.post("/webhook/exotel")
async def exotel_webhook(request: Request) -> Response:
    """Handle Exotel call status updates and DTMF responses."""
    body = await request.body()
    sig = request.headers.get("X-Exotel-Signature", "")

    if not _verify_exotel_hmac(body, sig):
        raise HTTPException(status_code=401, detail="invalid signature")

    form = await request.form()
    params: dict[str, Any] = dict(form)

    call_sid = str(params.get("CallSid", ""))
    call_status = str(params.get("CallStatus", "")).lower()
    digit = str(params.get("Digits", ""))
    step = str(params.get("step", ""))
    call_id_str = str(params.get("call_id", ""))

    log.info(
        "exotel_webhook call_sid=%s status=%s digit=%s step=%s",
        call_sid,
        call_status,
        digit,
        step,
    )

    # Resolve internal call_id and senior_id from DB
    call_id: uuid.UUID | None = None
    senior_id: uuid.UUID | None = None
    flow: str = ""
    language: str = "en"

    if call_id_str:
        with contextlib.suppress(ValueError):
            call_id = uuid.UUID(call_id_str)

    if call_id:
        row = await _get_call_row(call_id)
        if row:
            senior_id = uuid.UUID(str(row["senior_id"]))
            flow = str(row["flow"] or "")
            language = str(row["language"] or "en")

    # State transitions based on Exotel CallStatus
    if call_status in ("ringing", "in-progress") and call_id:
        status_map = {"ringing": "dialing", "in-progress": "in_progress"}
        await transition(call_id, status_map[call_status])

    elif call_status in ("completed", "busy", "failed", "no-answer") and call_id:
        if call_status == "completed":
            # If no DTMF was received, mark partial; resolved if DTMF was
            row2 = await _get_call_row(call_id)
            if row2 and not row2["dtmf_responses"]:
                await transition(call_id, "partial")
            else:
                await transition(call_id, "resolved")
        else:
            await transition(call_id, "failed")

    # Handle DTMF in Flow A
    if step == "dtmf" and digit and call_id and senior_id:
        xml = await _handle_flow_a_dtmf(call_id, senior_id, digit, flow, language)
        return Response(content=xml, media_type="application/xml")

    # Handle DTMF in Flow C wellness
    if step == "dtmf_wellness" and digit and call_id and senior_id:
        from app.ivr.symptom_tree import handle_dtmf

        xml = await handle_dtmf(call_id, senior_id, digit, current_node="root")
        return Response(content=xml, media_type="application/xml")

    if step == "dtmf_symptom" and digit and call_id and senior_id:
        from app.ivr.symptom_tree import handle_dtmf

        xml = await handle_dtmf(call_id, senior_id, digit, current_node="symptom_category")
        return Response(content=xml, media_type="application/xml")

    return Response(content="<Response><Hangup/></Response>", media_type="application/xml")



async def _handle_flow_a_dtmf(
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    digit: str,
    flow: str,
    language: str,
) -> str:
    from app.ivr.scripts.templates import render_flow_a_dtmf

    # Persist the event
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        event = "taken_via_ivr" if digit == "1" else "skipped_via_ivr"
        await conn.execute(
            """UPDATE ivr_call_log
               SET dtmf_responses = COALESCE(dtmf_responses,'{}')::jsonb || $2::jsonb,
                   status='resolved'
               WHERE id=$1""",
            call_id,
            f'{{"digit":"{digit}","event":"{event}"}}',
        )
        if digit == "1":
            await conn.execute(
                """INSERT INTO med_reminder_event (senior_id, medication_id, scheduled_for, event, event_at)
                   SELECT $1, m.id, NOW(), 'taken_via_ivr', NOW()
                   FROM medication m WHERE m.senior_id=$1
                   LIMIT 1""",
                senior_id,
            )
        await transition(call_id, "resolved")
    finally:
        await conn.close()

    return render_flow_a_dtmf(str(call_id), language, digit)


async def _get_call_row(call_id: uuid.UUID) -> asyncpg.Record | None:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        return await conn.fetchrow(
            "SELECT senior_id, flow, language, status, dtmf_responses FROM ivr_call_log WHERE id=$1",
            call_id,
        )
    finally:
        await conn.close()
