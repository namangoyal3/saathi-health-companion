"""arq worker: IVR outbound call jobs and retry scheduler (Day 3)."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings


async def place_ivr_call(
    ctx: dict[str, object],
    senior_id: str,
    flow: str,
    language: str,
    attempt: int = 1,
) -> dict[str, object]:
    """Place Exotel outbound call for Flow A/B/C. TODO Day 3."""
    return {
        "senior_id": senior_id,
        "flow": flow,
        "language": language,
        "attempt": attempt,
        "status": "pending_day3_implementation",
    }


async def retry_failed_ivr_calls(ctx: dict[str, object]) -> dict[str, object]:
    """Retry IVR calls that failed or went unanswered. TODO Day 3."""
    return {"status": "pending_day3_implementation"}


class WorkerSettings:
    functions: ClassVar[list[object]] = [place_ivr_call, retry_failed_ivr_calls]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 120
    max_jobs = 20
