"""Twilio outbound call client — fallback provider for non-Exotel markets.

DRY_RUN mode if TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER not set.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import asyncpg
import httpx

from app.config import settings

log = logging.getLogger(__name__)

_DRY_RUN = not (
    settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number
)


async def place_outbound(
    to_e164: str,
    flow: str,
    language: str,
    senior_id: uuid.UUID,
    *,
    call_id: uuid.UUID | None = None,
) -> str:
    """Fire a Twilio outbound call. Returns the call SID."""
    call_id = call_id or uuid.uuid4()
    twiml_url = f"{settings.app_base_url}/ivr/exoml/{flow}_{language}?call_id={call_id}"
    status_callback = f"{settings.app_base_url}/ivr/webhook/twilio"

    if _DRY_RUN:
        synthetic_sid = f"dry_run_twilio_{call_id}"
        log.info(
            "ivr_dry_run provider=twilio to=%s flow=%s lang=%s call_id=%s",
            to_e164,
            flow,
            language,
            call_id,
        )
        await _persist_call_log(
            call_id=call_id,
            senior_id=senior_id,
            provider="twilio",
            call_sid=synthetic_sid,
            flow=flow,
            language=language,
            status="queued",
        )
        return synthetic_sid

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls.json"
    async with httpx.AsyncClient(
        auth=(settings.twilio_account_sid, settings.twilio_auth_token), timeout=10.0
    ) as cx:
        r = await cx.post(
            url,
            data={
                "From": settings.twilio_from_number,
                "To": to_e164,
                "Url": twiml_url,
                "StatusCallback": status_callback,
                "StatusCallbackMethod": "POST",
                "TimeLimit": 90,
                "Record": "true",
            },
        )
    r.raise_for_status()
    call_sid: str = r.json()["sid"]

    await _persist_call_log(
        call_id=call_id,
        senior_id=senior_id,
        provider="twilio",
        call_sid=call_sid,
        flow=flow,
        language=language,
        status="queued",
    )
    log.info("ivr_queued provider=twilio call_sid=%s", call_sid)
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
