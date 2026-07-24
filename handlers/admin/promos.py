"""Promo codes management: create, list, delete, toggle active state."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database.db import async_session
from database.models import PromoCode
from keyboards.admin_kb import (
    admin_back_kb,
    admin_confirm_delete_kb,
    admin_promo_actions_kb,
    admin_promo_list_kb,
    admin_promo_menu_kb,
)
from states.order_states import AdminFlow
from utils.security import IsAdminFilter, get_admin_role_async, role_has_permission

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


async def _check_perm(telegram_id: int) -> bool:
    role = await get_admin_role_async(telegram_id)
    return role_has_permission(role, "promo")


@router.callback_query(F.data == "admin:promo")
async def cb_promo_menu(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await callback.message.edit_text(
        "🎟 <b>Promokodlar bo'limi</b>",
        reply_markup=admin_promo_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "promo:list")
async def cb_promo_list(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        promos = (
            await session.execute(
                select(
                    PromoCode.id, PromoCode.code, PromoCode.discount_value,
                    PromoCode.discount_type, PromoCode.is_active, PromoCode.uses_count
                ).order_by(PromoCode.id.desc())
            )
        ).all()
    await callback.message.edit_text(
        f"🎟 <b>Promokodlar ({len(promos)} ta)</b>",
        reply_markup=admin_promo_list_kb(promos),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("promo:open:"))
async def cb_promo_open(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        promo = await session.get(PromoCode, pid)
        if promo is None:
            await callback.answer("Topilmadi.", show_alert=True)
            return
        unit = "%" if promo.discount_type == "percent" else " so'm"
        text = (
            f"🎟 <b>Promokod: {promo.code}</b>\n\n"
            f"Tur: {promo.discount_type}\n"
            f"Qiymat: {promo.discount_value}{unit}\n"
            f"Min buyurtma: {promo.min_order_amount} so'm\n"
            f"Max foydalanish: {promo.max_uses or '∞'}\n"
            f"IsLATilgan: {promo.uses_count}\n"
            f"Faol: {'✅' if promo.is_active else '❌'}\n"
            f"Amal qilish muddati: {promo.valid_until.strftime('%d.%m.%Y %H:%M') if promo.valid_until else '∞'}\n"
        )
    await callback.message.edit_text(text, reply_markup=admin_promo_actions_kb(pid))
    await callback.answer()


@router.callback_query(F.data.startswith("promo:toggle:"))
async def cb_promo_toggle(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        promo = await session.get(PromoCode, pid)
        if promo is None:
            await callback.answer("Topilmadi.", show_alert=True)
            return
        promo.is_active = not promo.is_active
        await session.commit()
    await callback.answer("Holati o'zgartirildi ✅")
    await cb_promo_list(callback)


@router.callback_query(F.data.startswith("promo:del:"))
async def cb_promo_del_prompt(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await callback.message.edit_text(
        "❓ Promokodni o'chirishni tasdiqlaysizmi?",
        reply_markup=admin_confirm_delete_kb("promo", pid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:promo:"))
async def cb_promo_del_confirm(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        promo = await session.get(PromoCode, pid)
        if promo:
            await session.delete(promo)
            await session.commit()
    await callback.answer("O'chirildi ❌")
    await cb_promo_list(callback)


@router.callback_query(F.data.startswith("cancel_del:promo:"))
async def cb_promo_del_cancel(callback: CallbackQuery):
    await cb_promo_list(callback)


@router.callback_query(F.data == "promo:add")
async def cb_promo_add(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_promo_code)
    await callback.message.edit_text(
        "🎟 Yangi promokodni kiriting (masalan: <code>SALE20</code>):",
        reply_markup=admin_back_kb("admin:promo"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_promo_code)
async def process_promo_code_input(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    if not code or len(code) < 3:
        await message.answer("❌ Kamida 3 belgi kerak.")
        return
    async with async_session() as session:
        existing = (
            await session.execute(select(PromoCode).where(PromoCode.code == code))
        ).scalar_one_or_none()
        if existing:
            await message.answer("❌ Bunday promokod allaqachon mavjud.")
            return
    await state.update_data(promo_code=code)
    await state.set_state(AdminFlow.waiting_promo_value)
    await message.answer(
        "✏️ Endi chegirma qiymatini kiriting:\n\n"
        "<code>percent 20</code> — 20% chegirma\n"
        "<code>fixed 50000</code> — 50 000 so'm chegirma\n"
        "<code>percent 15 min 100000</code> — 15% faqat 100k+ buyurtmalar uchun"
    )


@router.message(AdminFlow.waiting_promo_value)
async def process_promo_value_input(message: Message, state: FSMContext):
    raw = (message.text or "").strip().lower()
    parts = raw.split()
    if not parts:
        await message.answer("❌ Format noto'g'ri.")
        return

    dtype = parts[0]
    if dtype not in ("percent", "fixed"):
        await message.answer("❌ Birinchi so'z 'percent' yoki 'fixed' bo'lishi kerak.")
        return
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("❌ Qiymat raqam bo'lishi kerak.")
        return
    value = int(parts[1])
    if dtype == "percent" and (value < 1 or value > 100):
        await message.answer("❌ Percent 1-100 oralig'ida bo'lishi kerak.")
        return
    if dtype == "fixed" and value < 1:
        await message.answer("❌ Fixed kamida 1 so'm bo'lishi kerak.")
        return

    min_amount = 0
    max_uses = 0
    if len(parts) >= 4 and parts[2] == "min" and parts[3].isdigit():
        min_amount = int(parts[3])
    if len(parts) >= 6 and parts[4] == "max" and parts[5].isdigit():
        max_uses = int(parts[6]) if len(parts) >= 7 and parts[6].isdigit() else 0

    data = await state.get_data()
    code = data["promo_code"]
    await state.update_data(
        promo_dtype=dtype, promo_value=value,
        promo_min=min_amount, promo_max=max_uses,
    )
    await state.set_state(AdminFlow.waiting_promo_until)
    await message.answer(
        "📅 Promokod amal qilish muddatini kiriting:\n\n"
        "<code>7d</code> — 7 kun\n"
        "<code>30d</code> — 30 kun\n"
        "<code>-</code> — cheksiz (hech qachon tugamaydi)"
    )


@router.message(AdminFlow.waiting_promo_until)
async def process_promo_until_input(message: Message, state: FSMContext):
    raw = (message.text or "").strip().lower()
    data = await state.get_data()
    await state.clear()

    valid_until = None
    if raw != "-":
        if raw.endswith("d") and raw[:-1].isdigit():
            days = int(raw[:-1])
            valid_until = datetime.now(timezone.utc) + timedelta(days=days)
        elif raw.endswith("h") and raw[:-1].isdigit():
            hours = int(raw[:-1])
            valid_until = datetime.now(timezone.utc) + timedelta(hours=hours)
        else:
            await message.answer("❌ Format: <code>7d</code> (7 kun) yoki <code>-</code> (cheksiz).")
            return

    async with async_session() as session:
        promo = PromoCode(
            code=data["promo_code"],
            discount_type=data["promo_dtype"],
            discount_value=data["promo_value"],
            min_order_amount=data["promo_min"],
            max_uses=data["promo_max"],
            valid_until=valid_until,
            is_active=True,
            created_by=message.from_user.id,
        )
        session.add(promo)
        await session.commit()

    unit = "%" if promo.discount_type == "percent" else " so'm"
    await message.answer(
        f"✅ Promokod yaratildi!\n\n"
        f"🎟 Kod: <code>{promo.code}</code>\n"
        f"📊 Chegirma: {promo.discount_value}{unit}\n"
        f"📅 Muddat: {promo.valid_until.strftime('%d.%m.%Y') if promo.valid_until else '∞'}",
        reply_markup=admin_back_kb("admin:promo"),
    )
