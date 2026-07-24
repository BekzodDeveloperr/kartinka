"""Application entry point: bot init, dispatcher, routers, scheduler, logging."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.db import init_db
from middlewares.flood_control import FloodControlMiddleware
from middlewares.state_sync import StateSyncMiddleware
from services.reminders import setup_scheduler

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)

log = logging.getLogger("bot")

bot: Bot | None = None


def _validate_token() -> None:
    if not BOT_TOKEN or "ExampleToken" in BOT_TOKEN:
        log.error(
            "BOT_TOKEN .env faylida to'g'ri sozlanmagan. .env.example dan nusxa oling."
        )
        sys.exit(1)


async def main() -> None:
    _validate_token()

    global bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # --- Middlewares ---
    dp.message.outer_middleware(FloodControlMiddleware())
    dp.callback_query.outer_middleware(FloodControlMiddleware())
    dp.message.middleware(StateSyncMiddleware())
    dp.callback_query.middleware(StateSyncMiddleware())

    # --- Database ---
    await init_db()
    log.info("Database initialized.")

    # --- Routers (admin first then user, so admin filters take priority) ---
    from handlers.admin import (
        admins_router,
        broadcast_router,
        catalog_router,
        orders_router,
        panel_router,
        promos_router,
        reports_router,
        reviews_router,
    )
    from handlers.user import (
        gallery_router,
        my_orders_router,
        order_flow_router,
        start_router,
    )

    dp.include_router(panel_router)
    dp.include_router(orders_router)
    dp.include_router(broadcast_router)
    dp.include_router(catalog_router)
    dp.include_router(promos_router)
    dp.include_router(admins_router)
    dp.include_router(reviews_router)
    dp.include_router(reports_router)

    dp.include_router(start_router)
    dp.include_router(order_flow_router)
    dp.include_router(gallery_router)
    dp.include_router(my_orders_router)

    # --- Scheduler ---
    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info("Scheduler started with timezone: %s", scheduler.timezone)

    # --- Run ---
    me = await bot.get_me()
    log.info("Bot @%s is up and running.", me.username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped by user.")
