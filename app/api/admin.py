"""Admin dashboard — single-page overview of system health, profiles,
vitals anomalies, wearable summaries, and conversation logs.

Routes:
  GET  /admin                   — HTML dashboard
  GET  /api/admin/state         — JSON snapshot of everything
  GET  /api/admin/chat/{chat_id} — bot_conv_memory tail for a chat (Priya, Lakshmi, any)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import asyncpg
import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

log = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])
_templates = Jinja2Templates(directory="app/templates")


def _pg_dsn() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(request: Request) -> Any:
    return _templates.TemplateResponse(request, "admin.html", {})


@router.get("/api/admin/state")
async def admin_state() -> dict[str, Any]:
    """Single snapshot used by the dashboard poller. Never throws — degrades field-by-field."""
    now = datetime.now(UTC).isoformat()

    health: dict[str, Any] = {
        "db": "unknown",
        "redis": "unknown",
        "alembic_revision": None,
        "anthropic_key": _has_key(settings.anthropic_api_key),
        "nvidia_key": _has_key(settings.nvidia_api_key),
        "openrouter_key": _has_key(settings.openrouter_api_key),
        "telegram_bot_token": _has_key(settings.telegram_bot_token),
        "elevenlabs_key": _has_key(settings.elevenlabs_api_key),
        "groq_key": _has_key(settings.groq_api_key),
        "wearable_hmac_configured": _has_key(settings.wearable_hmac_secret),
    }

    profiles: list[dict[str, Any]] = []
    app_users: list[dict[str, Any]] = []
    recent_anomalies: list[dict[str, Any]] = []
    recent_summaries: list[dict[str, Any]] = []
    recent_telegram_in: list[dict[str, Any]] = []
    agent_flag_counts: dict[str, int] = {}

    try:
        conn: asyncpg.Connection = await asyncpg.connect(dsn=_pg_dsn())
    except Exception as exc:
        health["db"] = f"down: {exc}"
        return {
            "timestamp": now,
            "health": health,
            "profiles": profiles,
            "app_users": app_users,
            "recent_anomalies": recent_anomalies,
            "recent_summaries": recent_summaries,
            "recent_telegram_in": recent_telegram_in,
            "agent_flag_counts": agent_flag_counts,
        }

    try:
        health["db"] = "ok"
        rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        health["alembic_revision"] = rev

        for row in await conn.fetch(
            """SELECT chat_id, name, language, conditions, family_chat_id,
                      updated_at
               FROM bot_profile
               ORDER BY updated_at DESC LIMIT 20"""
        ):
            profiles.append(
                {
                    "chat_id": row["chat_id"],
                    "name": row["name"],
                    "language": row["language"],
                    "conditions": row["conditions"],
                    "family_chat_id": row["family_chat_id"],
                    "updated_at": row["updated_at"].isoformat(),
                }
            )

        for row in await conn.fetch(
            """SELECT id, role, full_name, language, telegram_chat_id, created_at
               FROM app_user
               ORDER BY created_at DESC LIMIT 20"""
        ):
            app_users.append(
                {
                    "id": str(row["id"]),
                    "role": row["role"],
                    "full_name": row["full_name"],
                    "language": row["language"],
                    "telegram_chat_id": row["telegram_chat_id"],
                    "created_at": row["created_at"].isoformat(),
                }
            )

        for row in await conn.fetch(
            """SELECT va.marker, va.severity, va.value, va.threshold, va.narrative,
                      va.summary_date, va.alerted_at, va.created_at,
                      u.full_name AS senior_name
               FROM vitals_anomaly va
               LEFT JOIN app_user u ON u.id = va.senior_id
               ORDER BY va.created_at DESC LIMIT 15"""
        ):
            recent_anomalies.append(
                {
                    "senior_name": row["senior_name"] or "—",
                    "marker": row["marker"],
                    "severity": row["severity"],
                    "value": float(row["value"]),
                    "threshold": float(row["threshold"]),
                    "narrative": row["narrative"],
                    "summary_date": row["summary_date"].isoformat(),
                    "alerted": row["alerted_at"] is not None,
                    "created_at": row["created_at"].isoformat(),
                }
            )

        for row in await conn.fetch(
            """SELECT w.date, w.steps, w.avg_heart_rate, w.avg_spo2_pct,
                      w.sleep_minutes, w.hrv_rmssd, w.stress_score,
                      u.full_name AS senior_name
               FROM wearable_daily_summary w
               LEFT JOIN app_user u ON u.id = w.senior_id
               ORDER BY w.date DESC, w.updated_at DESC LIMIT 10"""
        ):
            recent_summaries.append(
                {
                    "senior_name": row["senior_name"] or "—",
                    "date": row["date"].isoformat(),
                    "steps": row["steps"],
                    "avg_heart_rate": row["avg_heart_rate"],
                    "avg_spo2_pct": row["avg_spo2_pct"],
                    "sleep_minutes": row["sleep_minutes"],
                    "hrv_rmssd": row["hrv_rmssd"],
                    "stress_score": row["stress_score"],
                }
            )

        for row in await conn.fetch(
            """SELECT t.received_at, t.message_type, t.intent, t.parsed_symptom,
                      t.raw_text, u.full_name AS senior_name
               FROM telegram_inbound t
               LEFT JOIN app_user u ON u.id = t.senior_id
               ORDER BY t.received_at DESC LIMIT 10"""
        ):
            recent_telegram_in.append(
                {
                    "senior_name": row["senior_name"] or "—",
                    "received_at": row["received_at"].isoformat(),
                    "message_type": row["message_type"],
                    "intent": row["intent"],
                    "parsed_symptom": row["parsed_symptom"],
                    "raw_text": (row["raw_text"] or "")[:160],
                }
            )

        for row in await conn.fetch(
            """SELECT severity, COUNT(*) AS n FROM agent_flag
               WHERE created_at > NOW() - INTERVAL '7 days'
               GROUP BY severity"""
        ):
            agent_flag_counts[row["severity"]] = row["n"]

    except Exception as exc:
        log.warning("admin_state_partial_err=%s", exc)
        health["db"] = f"partial: {exc}"
    finally:
        await conn.close()

    # Redis ping
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.ping()
        await redis.close()
        health["redis"] = "ok"
    except Exception as exc:
        health["redis"] = f"down: {str(exc)[:80]}"

    # Probe /health on self
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get("http://127.0.0.1:8080/health")
            health["self_health_http"] = r.status_code
    except Exception as exc:
        health["self_health_http"] = f"err: {str(exc)[:40]}"

    return {
        "timestamp": now,
        "health": health,
        "profiles": profiles,
        "app_users": app_users,
        "recent_anomalies": recent_anomalies,
        "recent_summaries": recent_summaries,
        "recent_telegram_in": recent_telegram_in,
        "agent_flag_counts": agent_flag_counts,
    }


@router.get("/api/admin/chat/{chat_id}")
async def admin_chat_tail(chat_id: int, limit: int = 30) -> dict[str, Any]:
    """Return the last N conversation turns for any Telegram chat_id (Priya, Lakshmi, etc)."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn=_pg_dsn())
    try:
        profile = await conn.fetchrow(
            "SELECT name, language, family_chat_id FROM bot_profile WHERE chat_id = $1",
            chat_id,
        )
        rows = await conn.fetch(
            """SELECT role, content, created_at FROM bot_conv_memory
               WHERE chat_id = $1 ORDER BY created_at DESC LIMIT $2""",
            chat_id,
            limit,
        )
    finally:
        await conn.close()

    turns = [
        {
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in reversed(rows)  # oldest first for natural reading
    ]
    return {
        "chat_id": chat_id,
        "profile": dict(profile) if profile else None,
        "turns": turns,
    }


def _has_key(value: str | None) -> bool:
    if not value:
        return False
    return not value.startswith("change-me")
