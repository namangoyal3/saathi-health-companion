"""Vitals anomaly detector orchestrator.

Entry point: process_summary(senior_id, date) runs VitalsAnomalyAgent on one
wearable_daily_summary row, persists anomaly rows, fires Telegram alerts for
HIGH/URGENT, and writes /memories/{senior_id}/vitals_flags.json.

Called inline from the Samsung webhook for low-latency demo, and also
available as an arq background task for decoupled processing.
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from pathlib import Path
from typing import Any, ClassVar

import asyncpg
from arq.connections import RedisSettings
from telegram import Bot
from telegram.constants import ParseMode

from app.agents.vitals_anomaly import DailySummaryInput, VitalsAnomaly
from app.agents.vitals_anomaly import run as classify
from app.config import settings

log = logging.getLogger(__name__)

_ALERT_SEVERITIES = {"HIGH", "URGENT"}
_SEVERITY_RANK = {"MEDIUM": 0, "HIGH": 1, "URGENT": 2}


def _pg_dsn() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _load_summary(
    conn: asyncpg.Connection, senior_id: uuid.UUID, date: datetime.date
) -> DailySummaryInput | None:
    row = await conn.fetchrow(
        """SELECT senior_id, date, steps, avg_heart_rate, sleep_minutes,
                  sleep_efficiency_pct, sleep_score, avg_spo2_pct,
                  avg_skin_temp_c, hrv_rmssd, stress_score, exercise_minutes
           FROM wearable_daily_summary
           WHERE senior_id = $1 AND date = $2""",
        senior_id,
        date,
    )
    if not row:
        return None
    return DailySummaryInput(
        senior_id=row["senior_id"],
        date=row["date"].isoformat(),
        steps=row["steps"] or 0,
        avg_heart_rate=row["avg_heart_rate"],
        sleep_minutes=row["sleep_minutes"],
        sleep_efficiency_pct=row["sleep_efficiency_pct"],
        sleep_score=row["sleep_score"],
        avg_spo2_pct=row["avg_spo2_pct"],
        avg_skin_temp_c=float(row["avg_skin_temp_c"]) if row["avg_skin_temp_c"] is not None else None,
        hrv_rmssd=row["hrv_rmssd"],
        stress_score=row["stress_score"],
        exercise_minutes=row["exercise_minutes"],
    )


async def _load_baseline_skin_temp(
    conn: asyncpg.Connection, senior_id: uuid.UUID, date: datetime.date
) -> float | None:
    """7-day rolling mean skin temp for the senior, excluding the target date."""
    row = await conn.fetchrow(
        """SELECT AVG(avg_skin_temp_c)::float AS mean
           FROM wearable_daily_summary
           WHERE senior_id = $1
             AND date >= $2::date - INTERVAL '7 days'
             AND date < $2::date
             AND avg_skin_temp_c IS NOT NULL""",
        senior_id,
        date,
    )
    return float(row["mean"]) if row and row["mean"] is not None else None


async def _persist_anomalies(
    conn: asyncpg.Connection,
    senior_id: uuid.UUID,
    summary_date: datetime.date,
    anomalies: list[VitalsAnomaly],
) -> None:
    for a in anomalies:
        await conn.execute(
            """INSERT INTO vitals_anomaly
               (senior_id, summary_date, marker, severity, value, threshold, narrative)
               VALUES ($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT (senior_id, summary_date, marker) DO UPDATE SET
                 severity = EXCLUDED.severity,
                 value = EXCLUDED.value,
                 threshold = EXCLUDED.threshold,
                 narrative = EXCLUDED.narrative""",
            senior_id,
            summary_date,
            a.marker,
            a.severity,
            float(a.value),
            float(a.threshold),
            a.narrative,
        )


def _write_memory(senior_id: uuid.UUID, anomalies: list[VitalsAnomaly]) -> None:
    mem_dir = settings.memory_root / str(senior_id)
    mem_dir.mkdir(parents=True, exist_ok=True)
    mem_path = mem_dir / "vitals_flags.json"

    existing: dict[str, Any] = {}
    if mem_path.exists():
        try:
            existing = json.loads(mem_path.read_text())
        except Exception:
            existing = {}

    prior: list[dict[str, Any]] = existing.get("recent_anomalies", [])
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    new_entries = [
        {
            "marker": a.marker,
            "severity": a.severity,
            "value": a.value,
            "threshold": a.threshold,
            "narrative": a.narrative,
            "recorded_at": now_iso,
        }
        for a in anomalies
    ]
    merged = (new_entries + prior)[:20]

    mem_path.write_text(
        json.dumps(
            {"last_updated": now_iso, "recent_anomalies": merged},
            ensure_ascii=False,
            indent=2,
        )
    )


async def _fire_telegram_alert(
    conn: asyncpg.Connection,
    senior_id: uuid.UUID,
    anomalies: list[VitalsAnomaly],
) -> bool:
    """Send Telegram URGENT/HIGH alert to the senior AND their linked guardian.

    Dual lookup:
      1. care_relationship (Day 1 schema) — if the senior is registered in the
         full app_user table with a linked guardian
      2. bot_profile.family_chat_id — the senior is a Telegram-only user whose
         guardian was paired via /link_guardian / /link_senior
    """
    high_urgent = [a for a in anomalies if a.severity in _ALERT_SEVERITIES]
    if not high_urgent:
        return False

    if not settings.telegram_bot_token:
        log.warning("telegram_bot_token not set — alert suppressed")
        return False

    highest = max(high_urgent, key=lambda a: _SEVERITY_RANK.get(a.severity, 0))

    # 1) full app_user → care_relationship lookup
    guardian_row = await conn.fetchrow(
        """SELECT u.telegram_chat_id, s.full_name, s.telegram_chat_id AS senior_chat_id
           FROM care_relationship cr
           JOIN app_user u ON u.id = cr.guardian_id
           JOIN app_user s ON s.id = cr.senior_id
           WHERE cr.senior_id = $1
           LIMIT 1""",
        senior_id,
    )

    # 2) bot-profile fallback: treat senior_id as the bot's chat_id interpretation.
    # This only fires when (a) there is no care_relationship match AND (b) the
    # caller stored the bot chat_id in app_user.telegram_chat_id at sync time.
    bot_row = None
    if not guardian_row:
        bot_row = await conn.fetchrow(
            """SELECT p.chat_id AS senior_chat_id, p.family_chat_id, p.name
               FROM app_user u
               JOIN bot_profile p ON p.chat_id = u.telegram_chat_id
               WHERE u.id = $1
               LIMIT 1""",
            senior_id,
        )

    senior_name = (
        (guardian_row and guardian_row["full_name"])
        or (bot_row and bot_row["name"])
        or "the senior"
    )
    header = f"⚠️ {highest.severity} — Vitals anomaly for {senior_name}"
    body_lines = "\n".join(f"• {a.narrative}" for a in high_urgent)
    text = (
        f"*{header}*\n\n{body_lines}\n\n"
        "_Informational summary — physician review recommended_"
    )

    recipients: list[int] = []
    if guardian_row:
        if guardian_row["telegram_chat_id"]:
            recipients.append(int(guardian_row["telegram_chat_id"]))
        if guardian_row["senior_chat_id"]:
            recipients.append(int(guardian_row["senior_chat_id"]))
    elif bot_row:
        recipients.append(int(bot_row["senior_chat_id"]))
        if bot_row["family_chat_id"]:
            recipients.append(int(bot_row["family_chat_id"]))

    if not recipients:
        log.info("vitals_alert_no_recipients senior=%s", str(senior_id))
        return False

    bot = Bot(token=settings.telegram_bot_token)
    sent_any = False
    for chat_id in set(recipients):
        try:
            await bot.send_message(
                chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN
            )
            sent_any = True
        except Exception as exc:
            log.warning("vitals_alert_failed chat=%s: %s", chat_id, exc)

    if sent_any:
        log.info(
            "vitals_alert_sent",
            senior_id=str(senior_id),
            severity=highest.severity,
            markers=[a.marker for a in high_urgent],
            recipients=list(set(recipients)),
        )
    return sent_any


async def process_summary(
    senior_id: uuid.UUID, summary_date: datetime.date | str
) -> dict[str, Any]:
    """Run VitalsAnomalyAgent on one daily summary, persist, alert, and write memory.

    Returns {"anomaly_count": N, "alerted": bool, "severities": [...]}.
    Idempotent: re-running for the same (senior_id, date) upserts anomaly rows.
    """
    if isinstance(summary_date, str):
        summary_date = datetime.date.fromisoformat(summary_date)

    conn: asyncpg.Connection = await asyncpg.connect(dsn=_pg_dsn())
    try:
        summary = await _load_summary(conn, senior_id, summary_date)
        if summary is None:
            log.warning("vitals_summary_not_found senior=%s date=%s", senior_id, summary_date)
            return {"anomaly_count": 0, "alerted": False, "severities": []}

        baseline_skin_temp = await _load_baseline_skin_temp(conn, senior_id, summary_date)

        anomalies = await classify(summary, baseline_skin_temp_c=baseline_skin_temp)

        await _persist_anomalies(conn, senior_id, summary_date, anomalies)
        alerted = await _fire_telegram_alert(conn, senior_id, anomalies)

        if alerted:
            await conn.execute(
                """UPDATE vitals_anomaly
                   SET alerted_at = NOW()
                   WHERE senior_id = $1 AND summary_date = $2
                     AND severity = ANY($3::text[])""",
                senior_id,
                summary_date,
                list(_ALERT_SEVERITIES),
            )

        if anomalies:
            _write_memory(senior_id, anomalies)

        return {
            "anomaly_count": len(anomalies),
            "alerted": alerted,
            "severities": sorted({a.severity for a in anomalies}),
            "markers": [a.marker for a in anomalies],
        }
    finally:
        await conn.close()


# arq background-task wrapper ----------------------------------------------------

async def detect_vitals_anomalies(
    ctx: dict[str, Any], senior_id: str, summary_date: str
) -> dict[str, Any]:
    """arq job — same semantics as process_summary(), called by webhook enqueue."""
    return await process_summary(uuid.UUID(senior_id), summary_date)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [detect_vitals_anomalies]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 60
    max_jobs = 5
