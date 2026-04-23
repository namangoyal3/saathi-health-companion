"""arq worker: lab PDF processing — Opus 4.7 vision pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, ClassVar

import asyncpg
import boto3
from arq.connections import RedisSettings

from app.config import settings
from app.labs.vision import parse_lab_pdf

log = logging.getLogger(__name__)


def _r2_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


async def process_lab_pdf(
    ctx: dict[str, object],
    panel_id: str,
    *,
    r2_key: str | None = None,
    local_path: str | None = None,
) -> dict[str, object]:
    """Parse a lab panel PDF and persist biomarkers to Postgres.

    Accepts either an R2 object key or a local file path (dev mode).
    Emits NOTIFY lab_parsed on completion so listeners can fan-out.
    """
    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )

    try:
        pdf_bytes: bytes | None = None

        if r2_key:
            s3 = _r2_client()
            resp = await asyncio.to_thread(s3.get_object, Bucket=settings.r2_bucket, Key=r2_key)
            pdf_bytes = resp["Body"].read()
        elif local_path:
            pdf_bytes = Path(local_path).read_bytes()
        else:
            await conn.execute(
                "UPDATE lab_panel SET status='failed', error='no_source' WHERE id=$1",
                uuid.UUID(panel_id),
            )
            return {"panel_id": panel_id, "status": "failed", "error": "no_source"}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)

        try:
            rows = parse_lab_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        if not rows:
            await conn.execute(
                "UPDATE lab_panel SET status='failed', error='no_biomarkers' WHERE id=$1",
                uuid.UUID(panel_id),
            )
            return {"panel_id": panel_id, "status": "failed", "error": "no_biomarkers"}

        collection_date = rows[0].collection_date or None
        lab_chain = rows[0].lab_chain

        await conn.execute(
            "UPDATE lab_panel SET status='parsed', collection_date=$2, lab_chain=$3 WHERE id=$1",
            uuid.UUID(panel_id),
            collection_date,
            lab_chain,
        )

        for row in rows:
            await conn.execute(
                """INSERT INTO lab_biomarker
                   (lab_panel_id, biomarker, value, unit, ref_low, ref_high, flag)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT DO NOTHING""",
                uuid.UUID(panel_id),
                row.biomarker,
                row.value,
                row.unit,
                row.ref_low,
                row.ref_high,
                row.flag,
            )

        # Notify subscribers — DDISubAgent and LabSubAgent can react
        await conn.execute(
            "SELECT pg_notify('lab_parsed', $1)",
            panel_id,
        )

        log.info("lab_pdf_parsed panel_id=%s biomarkers=%d", panel_id, len(rows))
        return {"panel_id": panel_id, "status": "parsed", "biomarkers": len(rows)}

    except Exception as exc:
        log.exception("lab_pdf_failed panel_id=%s", panel_id)
        with contextlib.suppress(Exception):
            await conn.execute(
                "UPDATE lab_panel SET status='failed', error=$2 WHERE id=$1",
                uuid.UUID(panel_id),
                str(exc)[:500],
            )
        raise
    finally:
        await conn.close()


class WorkerSettings:
    functions: ClassVar[list[object]] = [process_lab_pdf]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 300
    max_jobs = 10
