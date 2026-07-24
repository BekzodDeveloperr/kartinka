"""State-sync middleware.

On every incoming message or callback this middleware refreshes
users.last_active_at and resets reminder_sent when the user reappears
after a long absence (so a future drop-off reminder can be sent again).

Also reactivates 'tark_etdi' users back to 'start_bosdi' so they can
re-enter the funnel without stuck stats.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.db import async_session
from database.models import User
from sqlalchemy import select, update


class StateSyncMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            now = datetime.now(timezone.utc)
            async with async_session() as session:
                row = (
                    await session.execute(
                        select(User.reminder_sent, User.last_active_at, User.tag).where(
                            User.telegram_id == user.id
                        )
                    )
                ).first()
                if row is not None:
                    reminder_sent, last_active, tag = row
                    values: dict[str, Any] = {
                        "last_active_at": now,
                    }
                    if reminder_sent and last_active is not None:
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(tzinfo=timezone.utc)
                        if (now - last_active) > timedelta(hours=2):
                            values["reminder_sent"] = 0
                    # Reactivate abandoned users back to start so they re-enter the funnel
                    if tag == "tark_etdi":
                        values["tag"] = "start_bosdi"
                    await session.execute(
                        update(User).where(User.telegram_id == user.id).values(**values)
                    )
                    await session.commit()
        return await handler(event, data)
