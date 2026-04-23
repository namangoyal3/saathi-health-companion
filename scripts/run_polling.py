"""Run the Telegram bot in long-polling mode for local dev.

Does NOT use FastAPI — this is the fastest path to chat with the bot on
localhost without needing ngrok or a webhook URL.

Usage:
    uv run python scripts/run_polling.py

The scheduler (APScheduler) runs as well, so medication reminders and daily
summaries fire on the same cron as production.
"""

from __future__ import annotations

import logging
import sys

from telegram import Update
from telegram.ext import Application

from app.bot import db
from app.bot.application import build_application
from app.bot.scheduler import schedule_all_on_startup
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("saath.polling")


async def _post_init(app: Application) -> None:  # type: ignore[type-arg]
    await db.init_pool()
    await schedule_all_on_startup(app)
    me = await app.bot.get_me()
    log.info("Bot running as @%s (id=%d) — press Ctrl+C to stop.", me.username, me.id)


async def _post_shutdown(app: Application) -> None:  # type: ignore[type-arg]
    await db.close_pool()
    log.info("Bot stopped.")


def main() -> None:
    if not settings.telegram_bot_token:
        log.error("TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    app = build_application(settings.telegram_bot_token, with_updater=True)
    app.post_init = _post_init
    app.post_shutdown = _post_shutdown
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
