"""Admins management: list, add, change role, delete (super_admin only)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database.db import async_session
from database.models import AdminUser
from keyboards.admin_kb import admin_admins_list_kb, admin_back_kb, admin_role_picker_kb
from states.order_states import AdminFlow
from utils.security import IsAdminFilter, get_admin_role_async, role_has_permission

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


async def _check_super_admin(telegram_id: int) -> bool:
    role = await get_admin_role_async(telegram_id)
    return role == "super_admin"


@router.callback_query(F.data == "admin:admins")
async def cb_admin_admins_list(callback: CallbackQuery):
    if not await _check_super_admin(callback.from_user.id):
        await callback.answer("Faqat super_admin uchun.", show_alert=True)
        return
    async with async_session() as session:
        admins = (
            await session.execute(
                select(AdminUser.telegram_id, AdminUser.username, AdminUser.role)
                .order_by(AdminUser.id)
            )
        ).all()
    await callback.message.edit_text(
        "👮 <b>Adminlar ro'yxati</b>\n\nRolni o'zgartirish uchun adminni tanlang:",
        reply_markup=admin_admins_list_kb(admins),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:open:"))
async def cb_admin_open(callback: CallbackQuery):
    if not await _check_super_admin(callback.from_user.id):
        await callback.answer("Faqat super_admin uchun.", show_alert=True)
        return
    try:
        _, _, tg_id_str = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        adm = (
            await session.execute(
                select(AdminUser).where(AdminUser.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
    if adm is None:
        # Maybe it's an ADMIN_IDS admin (legacy, super_admin by default)
        from config import ADMIN_IDS
        if tg_id in ADMIN_IDS:
            await callback.message.edit_text(
                f"👑 {tg_id} — super_admin (.env dan)\n\n"
                "Bu admin .env faylidagi ADMIN_IDS ro'yxatidan. "
                "Uni o'chirish uchun .env ni tahrirlang.",
                reply_markup=admin_back_kb("admin:admins"),
            )
            await callback.answer()
            return
        await callback.answer("Admin topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        f"👮 <b>Admin: {adm.username or adm.telegram_id}</b>\n"
        f"Telegram ID: <code>{adm.telegram_id}</code>\n"
        f"Rol: {adm.role}\n\n"
        f"Yangi rolni tanlang:",
        reply_markup=admin_role_picker_kb(tg_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:set:"))
async def cb_admin_set_role(callback: CallbackQuery):
    if not await _check_super_admin(callback.from_user.id):
        await callback.answer("Faqat super_admin uchun.", show_alert=True)
        return
    try:
        _, _, tg_id_str, role = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    if role not in ("super_admin", "operator", "moliyachi"):
        await callback.answer()
        return
    async with async_session() as session:
        adm = (
            await session.execute(
                select(AdminUser).where(AdminUser.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if adm is None:
            adm = AdminUser(telegram_id=tg_id, role=role)
            session.add(adm)
        else:
            adm.role = role
        await session.commit()
    await callback.answer(f"Rol o'zgartirildi: {role}")
    await cb_admin_admins_list(callback)


@router.callback_query(F.data.startswith("adm:del:"))
async def cb_admin_del(callback: CallbackQuery):
    if not await _check_super_admin(callback.from_user.id):
        await callback.answer("Faqat super_admin uchun.", show_alert=True)
        return
    try:
        _, _, tg_id_str = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    if tg_id == callback.from_user.id:
        await callback.answer("O'zingizni o'chira olmaysiz!", show_alert=True)
        return
    async with async_session() as session:
        adm = (
            await session.execute(
                select(AdminUser).where(AdminUser.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if adm:
            await session.delete(adm)
            await session.commit()
    await callback.answer("Admin o'chirildi ❌")
    await cb_admin_admins_list(callback)


@router.callback_query(F.data == "adm:add")
async def cb_admin_add(callback: CallbackQuery, state: FSMContext):
    if not await _check_super_admin(callback.from_user.id):
        await callback.answer("Faqat super_admin uchun.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_new_admin_id)
    await callback.message.edit_text(
        "➕ <b>Yangi admin qo'shish</b>\n\n"
        "Yangi adminning Telegram ID sini yuboring (faqat raqam):\n"
        "(ID ni @userinfobot dan bilib olish mumkin)",
        reply_markup=admin_back_kb("admin:admins"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_new_admin_id)
async def process_new_admin_id(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Faqat raqam kiriting (Telegram ID).")
        return
    tg_id = int(raw)
    await state.clear()
    async with async_session() as session:
        existing = (
            await session.execute(
                select(AdminUser).where(AdminUser.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if existing:
            await message.answer(
                f"⚠️ {tg_id} allaqachon admin ro'yxatida (rol: {existing.role}).",
                reply_markup=admin_back_kb("admin:admins"),
            )
            return
        session.add(AdminUser(telegram_id=tg_id, role="operator", added_by=message.from_user.id))
        await session.commit()
    await message.answer(
        f"✅ {tg_id} operator sifatida qo'shildi.\n"
        "Rolni o'zgartirish uchun ro'yxatdan tanlang.",
        reply_markup=admin_back_kb("admin:admins"),
    )
