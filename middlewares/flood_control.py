"""Anti-spam / flood control middleware.

Prevents bot spamming while keeping normal gallery browsing smooth and fast.
Admins are completely exempt.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import is_admin


class FloodControlMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 50, window: int = 60, ban_sec: int = 3) -> None:
        super().__init__()
        self.limit = limit
        self.window = window
        self.ban_sec = ban_sec
        self._hits: dict[int, list[float]] = defaultdict(list)
        self._banned_until: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        uid = user.id

        # Admins are exempt from flood control
        if is_admin(uid):
            return await handler(event, data)

        now = time.time()

        # Still banned?
        if self._banned_until.get(uid, 0) > now:
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⚠️ Iltimos, biroz kuting...", show_alert=False)
                except Exception:
                    pass
            return None  # drop event during short cooldown

        # Clean old hits and add new
        recent = [t for t in self._hits[uid] if t > now - self.window]
        recent.append(now)
        self._hits[uid] = recent

        if len(recent) > self.limit:
            self._banned_until[uid] = now + self.ban_sec
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⚠️ Iltimos, tugmalarni biroz sekinroq bosing.", show_alert=True)
                except Exception:
                    pass
            elif isinstance(event, Message):
                try:
                    await event.answer("⚠️ Iltimos, biroz kuting.")
                except Exception:
                    pass
            return None

        return await handler(event, data)
