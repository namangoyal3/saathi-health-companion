"""IVR call state machine: QUEUED → DIALING → IN_PROGRESS → RESOLVED | PARTIAL | FAILED.

Retry logic: PARTIAL triggers re-queue at +10 min (+20 min on second), then
Telegram escalation to guardian after 3 failed attempts.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import asyncpg

from app.config import settings

log = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"dialing", "failed"},
    "dialing": {"in_progress", "failed"},
    "in_progress": {"resolved", "partial", "failed"},
    "partial": {"queued", "failed"},
}

# Retry delays in minutes: attempt 1→+10m, attempt 2→+20m, attempt 3→escalate
RETRY_DELAYS = [10, 20]


async def transition(call_id: uuid.UUID, new_status: str) -> None:
    """Move a call to a new status. Validates the transition."""
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        row = await conn.fetchrow(
            "SELECT status, attempt_number, senior_id, flow, language FROM ivr_call_log WHERE id=$1",
            call_id,
        )
        if not row:
            log.warning("ivr_transition call_id=%s not_found", call_id)
            return

        current = str(row["status"])
        allowed = VALID_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            log.warning(
                "ivr_invalid_transition call_id=%s %s→%s",
                call_id,
                current,
                new_status,
            )
            return

        now = datetime.now(UTC)
        if new_status in ("resolved", "failed", "partial"):
            await conn.execute(
                "UPDATE ivr_call_log SET status=$2, ended_at=$3 WHERE id=$1",
                call_id,
                new_status,
                now,
            )
        else:
            await conn.execute(
                "UPDATE ivr_call_log SET status=$2 WHERE id=$1",
                call_id,
                new_status,
            )

        log.info(
            "ivr_state_change call_id=%s %s→%s",
            call_id,
            current,
            new_status,
        )

        if new_status == "partial":
            await _handle_partial(
                conn,
                call_id=call_id,
                senior_id=uuid.UUID(str(row["senior_id"])),
                attempt=int(row["attempt_number"]),
                flow=str(row["flow"]),
                language=str(row["language"]),
            )
    finally:
        await conn.close()


async def _handle_partial(
    conn: asyncpg.Connection,
    *,
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    attempt: int,
    flow: str,
    language: str,
) -> None:
    if attempt <= len(RETRY_DELAYS):
        delay_minutes = RETRY_DELAYS[attempt - 1]
        log.info(
            "ivr_retry_scheduled call_id=%s attempt=%d delay_minutes=%d",
            call_id,
            attempt,
            delay_minutes,
        )
        # Enqueue retry via arq (deferred)
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job(
            "place_ivr_call",
            str(senior_id),
            flow,
            language,
            attempt + 1,
            _defer_by=delay_minutes * 60,
        )
        await pool.close()
    else:
        log.warning(
            "ivr_escalate_to_guardian senior_id=%s flow=%s all_attempts_exhausted",
            senior_id,
            flow,
        )
        await _escalate_guardian(conn, senior_id=senior_id, flow=flow)


async def _escalate_guardian(
    conn: asyncpg.Connection,
    *,
    senior_id: uuid.UUID,
    flow: str,
) -> None:
    """Send Telegram alert to guardian after all IVR retries exhausted."""
    try:
        row = await conn.fetchrow(
            """SELECT u.full_name, c.guardian_id FROM app_user u
               JOIN care_relationship c ON c.senior_id = u.id
               WHERE u.id = $1 LIMIT 1""",
            senior_id,
        )
        if not row:
            return

        senior_name = str(row["full_name"])
        guardian_id = uuid.UUID(str(row["guardian_id"]))

        guardian = await conn.fetchrow(
            "SELECT telegram_chat_id, language FROM app_user WHERE id=$1",
            guardian_id,
        )
        if not guardian or not guardian["telegram_chat_id"]:
            return

        chat_id = int(guardian["telegram_chat_id"])
        message = (
            f"⚠️ Unable to reach {senior_name} after 3 IVR attempts for flow {flow.upper()}. "
            "Please check in directly."
        )

        import asyncio

        # Use PTB to send — import here to avoid circular at module level
        import httpx

        from app.config import settings as _s

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: httpx.post(
                f"https://api.telegram.org/bot{_s.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=10,
            ),
        )
        log.info("ivr_guardian_escalation senior=%s guardian_chat=%d", senior_id, chat_id)
    except Exception as exc:
        log.warning("ivr_escalation_failed senior=%s err=%s", senior_id, exc)
