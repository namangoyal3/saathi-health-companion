"""Async DB adapter for bot-layer tables (bot_profile, bot_medication, etc.)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import asyncpg  # type: ignore[import]

from app.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]


def _dsn() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def init_pool() -> None:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(_dsn(), min_size=2, max_size=10)  # type: ignore[assignment]


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _p() -> asyncpg.Pool:  # type: ignore[type-arg]
    if _pool is None:
        raise RuntimeError("Bot DB pool not initialized — call init_pool() first")
    return _pool


def _decode_json_field(value: Any) -> Any:
    """Asyncpg may return JSONB as a Python object or a string; normalize to object."""
    if isinstance(value, str):
        return json.loads(value)
    return value if value is not None else []


# ---------- profiles ----------


async def save_profile(
    chat_id: int, name: str, language: str, conditions: list[str]
) -> dict[str, Any]:
    row = await _p().fetchrow(
        """
        INSERT INTO bot_profile (chat_id, name, language, conditions)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (chat_id) DO UPDATE
            SET name = EXCLUDED.name,
                language = EXCLUDED.language,
                conditions = EXCLUDED.conditions,
                updated_at = NOW()
        RETURNING *
        """,
        chat_id,
        name,
        language,
        json.dumps(conditions),
    )
    d = dict(row)
    d["conditions"] = _decode_json_field(d.get("conditions"))
    return d


async def get_profile(chat_id: int) -> dict[str, Any] | None:
    row = await _p().fetchrow("SELECT * FROM bot_profile WHERE chat_id = $1", chat_id)
    if row is None:
        return None
    d = dict(row)
    d["conditions"] = _decode_json_field(d.get("conditions"))
    return d


async def get_all_profiles() -> list[dict[str, Any]]:
    rows = await _p().fetch("SELECT * FROM bot_profile")
    result = []
    for row in rows:
        d = dict(row)
        d["conditions"] = _decode_json_field(d.get("conditions"))
        result.append(d)
    return result


async def delete_profile(chat_id: int) -> None:
    await _p().execute("DELETE FROM bot_profile WHERE chat_id = $1", chat_id)


# ---------- medications ----------


async def save_medication(
    chat_id: int,
    drug_name: str,
    dose: str | None,
    frequency: str | None,
    timings: list[str],
) -> dict[str, Any]:
    row = await _p().fetchrow(
        """
        INSERT INTO bot_medication (chat_id, drug_name, dose, frequency, timings)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        RETURNING *
        """,
        chat_id,
        drug_name,
        dose,
        frequency,
        json.dumps(timings),
    )
    d = dict(row)
    d["timings"] = _decode_json_field(d.get("timings"))
    d["id"] = str(d["id"])
    return d


async def get_medications(chat_id: int) -> list[dict[str, Any]]:
    rows = await _p().fetch(
        "SELECT * FROM bot_medication WHERE chat_id = $1 AND active = TRUE ORDER BY created_at",
        chat_id,
    )
    result = []
    for row in rows:
        d = dict(row)
        d["timings"] = _decode_json_field(d.get("timings"))
        d["id"] = str(d["id"])
        result.append(d)
    return result


async def get_medication(medication_id: str) -> dict[str, Any] | None:
    row = await _p().fetchrow(
        "SELECT * FROM bot_medication WHERE id = $1", uuid.UUID(medication_id)
    )
    if row is None:
        return None
    d = dict(row)
    d["timings"] = _decode_json_field(d.get("timings"))
    d["id"] = str(d["id"])
    return d


async def delete_medications_for_chat(chat_id: int) -> None:
    await _p().execute("DELETE FROM bot_medication WHERE chat_id = $1", chat_id)


# ---------- med_events ----------


async def save_med_event(
    chat_id: int,
    medication_id: str,
    drug_name: str,
    event: str,
    reminder_id: str,
    scheduled_for: str,
) -> dict[str, Any]:
    row = await _p().fetchrow(
        """
        INSERT INTO bot_med_event
            (chat_id, medication_id, drug_name, event, reminder_id, scheduled_for, event_date)
        VALUES ($1, $2, $3, $4, $5, $6, CURRENT_DATE)
        RETURNING *
        """,
        chat_id,
        uuid.UUID(medication_id),
        drug_name,
        event,
        reminder_id,
        scheduled_for,
    )
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("medication_id") is not None:
        d["medication_id"] = str(d["medication_id"])
    return d


async def get_med_events_today(chat_id: int) -> list[dict[str, Any]]:
    rows = await _p().fetch(
        "SELECT * FROM bot_med_event WHERE chat_id = $1 AND event_date = CURRENT_DATE",
        chat_id,
    )
    return [dict(r) for r in rows]


# ---------- snooze_counts ----------


async def get_snooze_count(reminder_id: str) -> int:
    row = await _p().fetchrow(
        "SELECT count FROM bot_snooze_count WHERE reminder_id = $1", reminder_id
    )
    return int(row["count"]) if row else 0


async def increment_snooze_count(reminder_id: str, chat_id: int) -> int:
    row = await _p().fetchrow(
        """
        INSERT INTO bot_snooze_count (reminder_id, chat_id, count)
        VALUES ($1, $2, 1)
        ON CONFLICT (reminder_id) DO UPDATE
            SET count = bot_snooze_count.count + 1,
                updated_at = NOW()
        RETURNING count
        """,
        reminder_id,
        chat_id,
    )
    return int(row["count"])


async def clear_snooze_count(reminder_id: str) -> None:
    await _p().execute("DELETE FROM bot_snooze_count WHERE reminder_id = $1", reminder_id)


# ---------- conversational memory ----------


async def append_conv(chat_id: int, role: str, content: str, keep: int = 10) -> None:
    """Append one turn to bot_conv_memory, trim to last `keep` turns for this chat."""
    await _p().execute(
        "INSERT INTO bot_conv_memory (chat_id, role, content) VALUES ($1, $2, $3)",
        chat_id,
        role,
        content,
    )
    await _p().execute(
        """
        DELETE FROM bot_conv_memory
         WHERE chat_id = $1
           AND id NOT IN (
               SELECT id FROM bot_conv_memory
                WHERE chat_id = $1
                ORDER BY created_at DESC
                LIMIT $2
           )
        """,
        chat_id,
        keep,
    )


async def get_conv(chat_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Last `limit` turns in chronological order (oldest → newest)."""
    rows = await _p().fetch(
        """
        SELECT role, content FROM bot_conv_memory
         WHERE chat_id = $1
         ORDER BY created_at DESC
         LIMIT $2
        """,
        chat_id,
        limit,
    )
    return list(reversed([{"role": r["role"], "content": r["content"]} for r in rows]))


async def clear_conv(chat_id: int) -> None:
    await _p().execute("DELETE FROM bot_conv_memory WHERE chat_id = $1", chat_id)


# ---------- guardian link ----------


async def create_link_code(senior_chat_id: int, code: str) -> None:
    """Store a new pairing code. Overwrites any prior code for this senior or code."""
    await _p().execute(
        "DELETE FROM bot_link_code WHERE senior_chat_id = $1 OR code = $2",
        senior_chat_id,
        code,
    )
    await _p().execute(
        "INSERT INTO bot_link_code (code, senior_chat_id) VALUES ($1, $2)",
        code,
        senior_chat_id,
    )


async def consume_link_code(code: str) -> int | None:
    """Atomically consume a pairing code. Returns the senior's chat_id or None if invalid."""
    row = await _p().fetchrow(
        """
        UPDATE bot_link_code
           SET consumed_at = NOW()
         WHERE code = $1
           AND consumed_at IS NULL
           AND expires_at > NOW()
         RETURNING senior_chat_id
        """,
        code,
    )
    return int(row["senior_chat_id"]) if row else None


async def set_family_chat_id(senior_chat_id: int, family_chat_id: int) -> None:
    await _p().execute(
        "UPDATE bot_profile SET family_chat_id = $1, updated_at = NOW() WHERE chat_id = $2",
        family_chat_id,
        senior_chat_id,
    )


async def get_seniors_for_guardian(guardian_chat_id: int) -> list[dict[str, Any]]:
    rows = await _p().fetch(
        "SELECT * FROM bot_profile WHERE family_chat_id = $1",
        guardian_chat_id,
    )
    result = []
    for row in rows:
        d = dict(row)
        d["conditions"] = _decode_json_field(d.get("conditions"))
        result.append(d)
    return result


# ---------- adherence streak ----------


async def get_adherence_streak(chat_id: int) -> int:
    """Consecutive days with no 'missed' doses (taken+skipped account for all expected)."""
    rows = await _p().fetch(
        """
        SELECT event_date, event
          FROM bot_med_event
         WHERE chat_id = $1
           AND event_date >= CURRENT_DATE - INTERVAL '30 days'
         ORDER BY event_date DESC
        """,
        chat_id,
    )
    if not rows:
        return 0

    meds_row = await _p().fetchrow(
        "SELECT COUNT(*) AS n, COALESCE(SUM(jsonb_array_length(timings)), 0) AS expected "
        "FROM bot_medication WHERE chat_id = $1 AND active = TRUE",
        chat_id,
    )
    expected_per_day = int(meds_row["expected"] or 0) if meds_row else 0
    if expected_per_day == 0:
        return 0

    # Group by date → counts of taken
    from collections import defaultdict
    by_date: dict[Any, dict[str, int]] = defaultdict(lambda: {"taken": 0, "skipped": 0})
    for r in rows:
        by_date[r["event_date"]][r["event"]] = by_date[r["event_date"]].get(r["event"], 0) + 1

    # Walk back from today; streak breaks on first day where taken < expected
    import datetime as _dt
    streak = 0
    d = _dt.date.today()
    for _ in range(30):
        rec = by_date.get(d, {"taken": 0, "skipped": 0})
        if rec.get("taken", 0) >= expected_per_day:
            streak += 1
        else:
            break
        d = d - _dt.timedelta(days=1)
    return streak
