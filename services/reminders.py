"""APScheduler jobs: drop-off reminders, tark_etdi sweep, daily & weekly reports."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update

from config import (
    DAILY_REPORT_HOUR,
    DAILY_REPORT_MIN,
    DROP_OFF_HOURS,
    REMINDER_DELAY_MIN,
    REMINDER_INTERVAL_MIN,
    SCHEDULER_TZ,
)
from database.db import async_session
from database.models import BotSetting, Order, User

log = logging.getLogger(__name__)


REMINDER_MESSAGES = {
    "galereyada_toxtadi": "🎨 Sizga yoqqan dizayn bo'lmadimi? Yangi variantlarni ko'rish uchun qayting 🙂",
    "xomashyoda_toxtadi": "🧵 Buyurtmangizni yakunlashni unutmang — atigi bir necha bosqich qoldi!",
    "narxni_kordi": "💰 Narx chiqdi, lekin tasdiqlamadingiz. Buyurtmani yakunlash uchun qayting!",
    "mahsulot_tanladi": "🛒 Savatingizda mahsulot bor — yakunlashni unutmang!",
    "turni_tanladi": "🖼 Turni tanlagansiz, davom ettiring — galereyani ko'ring!",
}

TERMINAL_TAGS = {
    "buyurtma_berdi",
    "avans_kutilmoqda",
    "jarayonda",
    "tayyor",
    "yetkazildi",
    "bekor_qildi",
    "tark_etdi",
}


async def send_dropoff_reminders(bot) -> None:
    """Every REMINDER_INTERVAL_MIN: send ONE reminder to inactive users mid-flow."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=REMINDER_DELAY_MIN)
    async with async_session() as session:
        users = (
            await session.execute(
                select(User).where(
                    User.last_active_at < cutoff,
                    User.reminder_sent == 0,
                    ~User.tag.in_(TERMINAL_TAGS),
                )
            )
        ).scalars().all()
        if not users:
            return

        # Optional drop-off notification to admins
        notify_dropoff = False
        setting = await session.get(BotSetting, "notify_dropoff")
        if setting and setting.value == "1":
            notify_dropoff = True

        from config import ADMIN_IDS
        from database.models import AdminUser
        admin_ids = set(ADMIN_IDS)
        admin_ids.update((await session.execute(select(AdminUser.telegram_id))).scalars().all())

        if notify_dropoff and users:
            from utils.security import get_admin_role_async, role_has_permission
            notify_text = (
                f"⚠️ <b>Drop-off ogohlantirishi</b>\n\n"
                f"{len(users)} ta foydalanuvchi hozircha buyurtmani yakunlamagan:\n"
            )
            for u in users[:10]:
                notify_text += f"   • {u.full_name or u.telegram_id} ({u.tag})\n"
            if len(users) > 10:
                notify_text += f"   ...va yana {len(users) - 10} ta\n"
            for aid in admin_ids:
                role = await get_admin_role_async(aid)
                if role_has_permission(role, "stats"):
                    try:
                        await bot.send_message(aid, notify_text)
                    except Exception:
                        pass

        for user in users:
            msg = REMINDER_MESSAGES.get(user.tag)
            if not msg:
                continue
            try:
                await bot.send_message(user.telegram_id, msg)
            except Exception as e:
                log.warning("Reminder failed for user %s: %s", user.telegram_id, e)
            await session.execute(
                update(User).where(User.id == user.id).values(reminder_sent=1)
            )
        await session.commit()


async def mark_tark_etdi() -> None:
    """Mark users inactive > DROP_OFF_HOURS as 'tark_etdi'."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DROP_OFF_HOURS)
    async with async_session() as session:
        result = await session.execute(
            update(User)
            .where(
                User.last_active_at < cutoff,
                ~User.tag.in_(TERMINAL_TAGS),
            )
            .values(tag="tark_etdi")
        )
        await session.commit()
        if result.rowcount:
            log.info("Marked %s users as 'tark_etdi'", result.rowcount)


async def daily_report_job(bot) -> None:
    from services.reports import build_daily_report
    from config import ADMIN_IDS
    from database.models import AdminUser
    async with async_session() as session:
        text = await build_daily_report(session, target_date=datetime.now(timezone.utc))
    admin_ids = set(ADMIN_IDS)
    async with async_session() as session:
        admin_ids.update((await session.execute(select(AdminUser.telegram_id))).scalars().all())
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            log.warning("Daily report send failed for admin %s: %s", admin_id, e)


async def weekly_report_job(bot) -> None:
    from services.reports import build_weekly_report
    from config import ADMIN_IDS
    from database.models import AdminUser
    async with async_session() as session:
        text = await build_weekly_report(session)
    admin_ids = set(ADMIN_IDS)
    async with async_session() as session:
        admin_ids.update((await session.execute(select(AdminUser.telegram_id))).scalars().all())
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            log.warning("Weekly report send failed for admin %s: %s", admin_id, e)


def setup_scheduler(bot) -> AsyncIOScheduler:
    """Configure scheduler with proper timezone (default Asia/Tashkent)."""
    scheduler = AsyncIOScheduler(timezone=SCHEDULER_TZ)

    scheduler.add_job(
        send_dropoff_reminders,
        trigger=IntervalTrigger(minutes=REMINDER_INTERVAL_MIN),
        args=[bot],
        id="dropoff_reminder",
        replace_existing=True,
    )

    scheduler.add_job(
        mark_tark_etdi,
        trigger=IntervalTrigger(hours=1),
        id="tark_etdi_sweep",
        replace_existing=True,
    )

    # Daily report at configured hour in SCHEDULER_TZ (default 21:00 Asia/Tashkent)
    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MIN, timezone=SCHEDULER_TZ),
        args=[bot],
        id="daily_report",
        replace_existing=True,
    )

    # Weekly report — Monday at same time
    scheduler.add_job(
        weekly_report_job,
        trigger=CronTrigger(day_of_week="mon", hour=DAILY_REPORT_HOUR, minute=DAILY_REPORT_MIN, timezone=SCHEDULER_TZ),
        args=[bot],
        id="weekly_report",
        replace_existing=True,
    )

    return scheduler
