"""Exotel outbound call client.

If EXOTEL_SID / EXOTEL_TOKEN / EXOTEL_FROM_NUMBER are not set, runs in DRY_RUN mode:
logs what would have been sent and returns a synthetic call_sid.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import asyncpg
import httpx

from app.config import settings

log = logging.getLogger(__name__)

_DRY_RUN = not (settings.exotel_sid and settings.exotel_token and settings.exotel_from_number)


async def place_outbound(
    to_e164: str,
    flow: str,
    language: str,
    senior_id: uuid.UUID,
    *,
    call_id: uuid.UUID | None = None,
) -> str:
    """Fire an Exotel outbound call.

    Returns the provider call_sid. Persists an ivr_call_log row in status=queued.
    """
    call_id = call_id or uuid.uuid4()
    exoml_url = f"{settings.app_base_url}/ivr/exoml/{flow}_{language}?call_id={call_id}"
    status_callback = f"{settings.app_base_url}/ivr/webhook/exotel"

    if _DRY_RUN:
        synthetic_sid = f"dry_run_{call_id}"
        log.info(
            "ivr_dry_run provider=exotel to=%s flow=%s lang=%s call_id=%s",
            to_e164,
            flow,
            language,
            call_id,
        )
        await _persist_call_log(
            call_id=call_id,
            senior_id=senior_id,
            provider="exotel",
            call_sid=synthetic_sid,
            flow=flow,
            language=language,
            status="queued",
        )
        return synthetic_sid

    url = f"https://api.exotel.com/v1/Accounts/{settings.exotel_sid}/Calls/connect"
    async with httpx.AsyncClient(
        auth=(settings.exotel_sid, settings.exotel_token), timeout=10.0
    ) as cx:
        r = await cx.post(
            url,
            data={
                "From": settings.exotel_from_number,
                "To": to_e164,
                "Url": exoml_url,
                "CallerId": settings.exotel_from_number,
                "TimeLimit": 90,
                "TimeOut": 25,
                "StatusCallback": status_callback,
                "StatusCallbackContentType": "application/json",
                "Record": "true",
                "CustomField": f"flow={flow};senior_id={senior_id};call_id={call_id}",
            },
        )
    r.raise_for_status()
    call_sid: str = r.json()["Call"]["Sid"]

    await _persist_call_log(
        call_id=call_id,
        senior_id=senior_id,
        provider="exotel",
        call_sid=call_sid,
        flow=flow,
        language=language,
        status="queued",
    )
    log.info("ivr_queued provider=exotel call_sid=%s flow=%s lang=%s", call_sid, flow, language)
    return call_sid


async def _persist_call_log(
    *,
    call_id: uuid.UUID,
    senior_id: uuid.UUID,
    provider: str,
    call_sid: str,
    flow: str,
    language: str,
    status: str,
) -> None:
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute(
            """INSERT INTO ivr_call_log
               (id, senior_id, provider, call_sid, flow, language, status, started_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
               ON CONFLICT DO NOTHING""",
            call_id,
            senior_id,
            provider,
            call_sid,
            flow,
            language,
            status,
            datetime.now(UTC),
        )
    finally:
        await conn.close()
