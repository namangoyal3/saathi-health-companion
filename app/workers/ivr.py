"""arq worker: IVR outbound call jobs — polls auto_skip rows, retries PARTIAL calls."""

from __future__ import annotations

import logging
import uuid
from typing import ClassVar

import asyncpg
from arq.connections import RedisSettings

from app.config import settings

log = logging.getLogger(__name__)


async def place_ivr_call(
    ctx: dict[str, object],
    senior_id: str,
    flow: str,
    language: str,
    attempt: int = 1,
) -> dict[str, object]:
    """Place an Exotel outbound call for a given senior and flow."""
    from app.ivr.exotel import place_outbound

    call_id = uuid.uuid4()
    try:
        call_sid = await place_outbound(
            to_e164=await _get_phone(uuid.UUID(senior_id)),
            flow=flow,
            language=language,
            senior_id=uuid.UUID(senior_id),
            call_id=call_id,
        )
        log.info(
            "ivr_job_placed senior=%s flow=%s attempt=%d call_sid=%s",
            senior_id,
            flow,
            attempt,
            call_sid,
        )
        return {
            "senior_id": senior_id,
            "flow": flow,
            "language": language,
            "attempt": attempt,
            "call_sid": call_sid,
            "status": "queued",
        }
    except Exception as exc:
        log.exception("ivr_job_failed senior=%s flow=%s attempt=%d", senior_id, flow, attempt)
        return {
            "senior_id": senior_id,
            "flow": flow,
            "attempt": attempt,
            "status": "error",
            "error": str(exc),
        }


async def poll_auto_skip_for_ivr(ctx: dict[str, object]) -> dict[str, object]:
    """Every 5 minutes: find med_reminder_event rows with status='auto_skip' in the last hour.

    For each, enqueue an IVR Flow A call if not already called.
    """
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    queued = 0
    try:
        rows = await conn.fetch(
            """SELECT DISTINCT mre.senior_id, u.phone, u.language
               FROM med_reminder_event mre
               JOIN app_user u ON u.id = mre.senior_id
               WHERE mre.event = 'auto_skip'
                 AND mre.event_at > NOW() - INTERVAL '1 hour'
                 AND NOT EXISTS (
                     SELECT 1 FROM ivr_call_log il
                     WHERE il.senior_id = mre.senior_id
                       AND il.flow = 'flowA'
                       AND il.started_at > NOW() - INTERVAL '1 hour'
                 )
               LIMIT 20"""
        )

        from arq import create_pool

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        for row in rows:
            lang = str(row["language"] or "hi")
            await pool.enqueue_job(
                "place_ivr_call",
                str(row["senior_id"]),
                "flowA",
                lang,
                1,
            )
            queued += 1
            log.info("ivr_auto_skip_enqueued senior=%s lang=%s", row["senior_id"], lang)
        await pool.close()
    finally:
        await conn.close()

    return {"queued": queued}


async def _get_phone(senior_id: uuid.UUID) -> str:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        row = await conn.fetchrow("SELECT phone FROM app_user WHERE id=$1", senior_id)
        if not row or not row["phone"]:
            raise ValueError(f"No phone for senior {senior_id}")
        return str(row["phone"])
    finally:
        await conn.close()


class WorkerSettings:
    functions: ClassVar[list[object]] = [place_ivr_call, poll_auto_skip_for_ivr]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 120
    max_jobs = 20
    cron_jobs: ClassVar[list[object]] = []
