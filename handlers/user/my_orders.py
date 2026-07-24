"""'My orders' view for the regular user."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from database.db import async_session
from database.models import Order, User
from keyboards.user_kb import main_menu_kb, orders_list_kb
from utils import format_order_details
from utils.i18n import get_user_language, t
from utils.security import is_admin_async
from utils.formatting import format_price

router = Router()

PER_PAGE = 5


async def _fetch_orders(session, telegram_id: int, page: int):
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        return [], 0
    total = (
        await session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.user_id == user.id, Order.status != "draft")
        )
    ).scalar_one()
    res = await session.execute(
        select(Order.id, Order.order_number, Order.status, Order.total_price, Order.created_at)
        .where(Order.user_id == user.id, Order.status != "draft")
        .order_by(Order.created_at.desc())
        .limit(PER_PAGE)
        .offset(page * PER_PAGE)
    )
    return res.all(), total


async def show_my_orders(callback: CallbackQuery, state: FSMContext, page: int = 0):
    lang = await get_user_language(callback.from_user.id)
    async with async_session() as session:
        rows, total = await _fetch_orders(session, callback.from_user.id, page)
    await callback.message.edit_text(
        t(lang, "my_orders_title", total=total),
        reply_markup=orders_list_kb(rows, page=page, per_page=PER_PAGE, total=total, lang=lang),
    )
    await callback.answer()


async def show_my_orders_message(message: Message, state: FSMContext, page: int = 0):
    lang = await get_user_language(message.from_user.id)
    async with async_session() as session:
        rows, total = await _fetch_orders(session, message.from_user.id, page)
    await message.answer(
        t(lang, "my_orders_title", total=total),
        reply_markup=orders_list_kb(rows, page=page, per_page=PER_PAGE, total=total, lang=lang),
    )


@router.callback_query(F.data.startswith("orders:page:"))
async def cb_orders_page(callback: CallbackQuery, state: FSMContext):
    try:
        _, _, page_str = callback.data.split(":")
        page = int(page_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await show_my_orders(callback, state, page)


@router.callback_query(F.data.startswith("orders:open:"))
async def cb_open_order(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    try:
        _, _, oid_str = callback.data.split(":")
        order_id = int(oid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order is None or order.user_id is None:
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        user = await session.get(User, order.user_id)
        if user is None or user.telegram_id != callback.from_user.id:
            await callback.answer("Bu buyurtma sizga tegishli emas.", show_alert=True)
            return
        summary = await format_order_details(session, order, lang)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ " + ("Orqaga" if lang=="uz" else ("Назад" if lang=="ru" else "Back")), callback_data="menu:my_orders")
    await callback.message.edit_text(summary, reply_markup=kb.as_markup())
    await callback.answer()
