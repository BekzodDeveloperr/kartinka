"""Security: admin filter, role-based filter, small helpers.

Admin-only commands/buttons are silently ignored for non-admin users
so that the admin panel is effectively invisible to ordinary users.

Roles:
  - super_admin  : full access (panel, broadcast, settings, add admins, catalog)
  - operator     : orders management + catalog + statistics
  - moliyachi    : orders (financial view) + statistics + Excel export
"""
from __future__ import annotations

from typing import Any, Union

from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from database.db import async_session
from database.models import AdminUser
from sqlalchemy import select


# All known admin roles
ROLES = ("super_admin", "operator", "moliyachi")


def _role_permissions() -> dict[str, set[str]]:
    """Map role -> set of allowed permission tags."""
    return {
        "super_admin": {
            "panel", "orders", "broadcast", "catalog", "stats",
            "export", "settings", "admins", "promo",
        },
        "operator": {
            "panel", "orders", "catalog", "stats", "promo",
        },
        "moliyachi": {
            "panel", "orders", "stats", "export", "promo",
        },
    }


def role_has_permission(role: str | None, permission: str) -> bool:
    if role is None:
        return False
    return permission in _role_permissions().get(role, set())


async def get_admin_role_async(telegram_id: int) -> str | None:
    """Fetch admin role from DB. Returns None for non-admins."""
    # Fast path: IDs in ADMIN_IDS are always super_admin
    if telegram_id in ADMIN_IDS:
        return "super_admin"
    async with async_session() as s:
        row = (
            await s.execute(
                select(AdminUser.role).where(AdminUser.telegram_id == telegram_id)
            )
        ).scalar_one_or_none()
        return row


async def is_admin_async(telegram_id: int) -> bool:
    return (await get_admin_role_async(telegram_id)) is not None


class IsAdminFilter(BaseFilter):
    """Reusable filter: passes only for any-role admin (super/operator/moliyachi)."""

    async def __call__(self, event: Union[Message, CallbackQuery, Any]) -> bool:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        return await is_admin_async(user.id)


class HasPermissionFilter(BaseFilter):
    """Pass only if the user has a specific permission via their role."""

    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(self, event: Union[Message, CallbackQuery, Any]) -> bool:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        role = await get_admin_role_async(user.id)
        return role_has_permission(role, self.permission)


def require_admin_silent(user_id: int) -> bool:
    """Sync helper (legacy, no DB) — for code that doesn't await."""
    return user_id in ADMIN_IDS


def get_bot() -> Bot | None:
    """Get the current aiogram Bot instance without circular import.

    Uses aiogram's contextual var — works inside any handler.
    """
    try:
        return Bot.get_current()
    except Exception:
        return None


async def get_admin_username_async() -> str:
    """Fetch admin username from DB setting or config fallback."""
    from database.models import BotSetting
    from config import ADMIN_USERNAME
    async with async_session() as s:
        setting = await s.get(BotSetting, "admin_username")
        if setting and setting.value:
            return setting.value.strip().lstrip("@")
    return ADMIN_USERNAME.strip().lstrip("@")
