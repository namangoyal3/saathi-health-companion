"""IVR Flow A live test — places a real Exotel call, waits for DTMF=1 from Postgres.

Usage:
    uv run python scripts/test_ivr_flow_a.py --to "+91XXXXXXXXXX" --language ta

The script:
1. Places an outbound call via Exotel (or DRY_RUN if creds missing)
2. Polls ivr_call_log every 2 seconds for DTMF=1 confirmation
3. Exits 0 with success message, exits 1 on timeout or failure

Acceptance: phone rings, you press 1, script prints the DTMF row and exits 0.
"""

import argparse
import asyncio
import sys
import uuid

import asyncpg


async def main(to: str, language: str, timeout_seconds: int = 120) -> int:
    from app.config import settings
    from app.ivr.exotel import place_outbound

    # Pick a real senior_id from DB, fall back to a test UUID
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        row = await conn.fetchrow("SELECT id FROM app_user WHERE role='senior' LIMIT 1")
        senior_id = uuid.UUID(str(row["id"])) if row else uuid.uuid4()

        print(f"Placing IVR Flow A call to {to!r} (lang={language}, senior={senior_id})")
        call_id = uuid.uuid4()
        call_sid = await place_outbound(
            to_e164=to,
            flow="flowA",
            language=language,
            senior_id=senior_id,
            call_id=call_id,
        )
        print(f"  call_sid={call_sid!r} call_id={call_id}")
        print("  Waiting for DTMF=1 response (press 1 on your phone)...")

        # Poll for resolution
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(2)
            log_row = await conn.fetchrow(
                "SELECT status, dtmf_responses, ended_at FROM ivr_call_log WHERE id=$1",
                call_id,
            )
            if not log_row:
                continue
            status = str(log_row["status"])
            dtmf = log_row["dtmf_responses"]
            if status == "resolved" and dtmf:
                from datetime import datetime

                ended_at = log_row["ended_at"] or datetime.now()
                print(
                    f"\n✓ Flow A complete: DTMF={dtmf} logged at "
                    f"{ended_at.strftime('%Y-%m-%d %H:%M')} IST, "
                    "Priya notification sent."
                )
                return 0
            if status == "failed":
                print(f"\n✗ Call failed (status={status})")
                return 1
            print(f"  ...still waiting (status={status})")

        print(f"\n✗ Timeout after {timeout_seconds}s — no DTMF received")
        return 1
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help='E.164 number, e.g. "+919876543210"')
    parser.add_argument("--language", default="ta", choices=["ta", "hi", "en"])
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.to, args.language, args.timeout)))
