"""Admin panel entry: /admin command + main panel rendering (role-aware)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from database.db import async_session
from database.models import AdminUser, Order, User
from keyboards.admin_kb import admin_back_kb, admin_panel_kb, admin_stats_kb
from states.order_states import AdminFlow
from utils.security import (
    HasPermissionFilter,
    IsAdminFilter,
    get_admin_role_async,
    role_has_permission,
)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


async def _get_permissions(telegram_id: int) -> set[str]:
    role = await get_admin_role_async(telegram_id)
    if role is None:
        return set()
    from utils.security import _role_permissions
    return _role_permissions().get(role, set())


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    perms = await _get_permissions(message.from_user.id)
    if not perms:
        # Not an admin at all (already filtered, but double-check)
        return
    await message.answer(
        "🔧 <b>Admin panel</b>\n\nBo'limni tanlang:",
        reply_markup=admin_panel_kb(perms),
    )


async def edit_or_send_panel(callback: CallbackQuery, text: str, reply_markup=None):
    if callback.message and callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup)
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "admin:panel")
async def cb_admin_panel(callback: CallbackQuery):
    perms = await _get_permissions(callback.from_user.id)
    await edit_or_send_panel(
        callback,
        "🔧 <b>Admin panel</b>\n\nBo'limni tanlang:",
        reply_markup=admin_panel_kb(perms),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:close")
async def cb_admin_close(callback: CallbackQuery):
    await callback.message.edit_text("Admin panel yopildi. /admin bilan qaytadan oching.")
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def cb_admin_users(callback: CallbackQuery):
    """Quick user overview."""
    perms = await _get_permissions(callback.from_user.id)
    if "users" not in perms and "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        total_users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        by_tag = (
            await session.execute(
                select(User.tag, func.count()).group_by(User.tag)
            )
        ).all()
        total_orders = (await session.execute(
            select(func.count()).select_from(Order).where(Order.status != "draft")
        )).scalar_one()
    lines = [f"👥 <b>Foydalanuvchilar:</b> {total_users}", f"🧾 <b>Buyurtmalar:</b> {total_orders}", "", "📊 Tag bo'yicha:"]
    for tag, cnt in by_tag:
        lines.append(f"   • {tag}: {cnt}")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:settings")
async def cb_admin_settings(callback: CallbackQuery):
    """Settings panel."""
    perms = await _get_permissions(callback.from_user.id)
    if "settings" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    from database.models import BotSetting
    from utils.security import get_admin_username_async
    async with async_session() as session:
        rows = (await session.execute(select(BotSetting))).scalars().all()
    settings = {s.key: s.value for s in rows}
    current_username = await get_admin_username_async()
    from keyboards.admin_kb import admin_settings_kb
    text = (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🔗 <b>Joriy Admin Telegram Username:</b> @{current_username}\n\n"
        "(Mijozlar to'lov uchun bog'langanda ushbu username'ga yo'naltiriladi)"
    )
    await callback.message.edit_text(text, reply_markup=admin_settings_kb(settings, current_username))
    await callback.answer()


@router.callback_query(F.data == "set:change_admin_username")
async def cb_change_admin_username(callback: CallbackQuery, state: FSMContext):
    perms = await _get_permissions(callback.from_user.id)
    if "settings" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    from states.order_states import AdminFlow
    await state.set_state(AdminFlow.waiting_admin_username_setting)
    await callback.message.edit_text(
        "✏️ <b>Yangi Admin Telegram Username'ini yuboring:</b>\n\n"
        "(Masalan: @kartinkauz_admin yoki kartinkauz_admin)",
        reply_markup=admin_back_kb("admin:settings"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_admin_username_setting)
async def admin_change_username_setting_handler(message: Message, state: FSMContext):
    raw = (message.text or "").strip().lstrip("@")
    await state.clear()
    if not raw or len(raw) < 3:
        await message.answer("❌ Noto'g'ri username. Kamida 3 ta belgi kerak.")
        return
    from database.models import BotSetting
    async with async_session() as session:
        setting = await session.get(BotSetting, "admin_username")
        if setting is None:
            setting = BotSetting(key="admin_username", value=raw)
            session.add(setting)
        else:
            setting.value = raw
        await session.commit()
    await message.answer(
        f"✅ <b>Admin username muvaffaqiyatli o'zgartirildi:</b> @{raw}\n\n"
        f"Endi mijozlar to'lov tugmasini bossa <code>t.me/{raw}</code> ga yo'naltiriladi.",
        reply_markup=admin_back_kb("admin:settings"),
    )


@router.callback_query(F.data == "admin:export")
async def cb_admin_export(callback: CallbackQuery):
    """Trigger Excel export."""
    perms = await _get_permissions(callback.from_user.id)
    if "export" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    from handlers.admin.reports import export_orders_xlsx
    await export_orders_xlsx(callback)
