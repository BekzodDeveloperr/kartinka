"""User entry point: /start, registration (name/phone/address), main menu, language picker."""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, Contact, Location
from sqlalchemy import delete, select, update

from config import ADMIN_USERNAME
from database.db import async_session
from database.models import Order, User
from keyboards.user_kb import (
    cancel_kb,
    contact_request_kb,
    hide_reply_kb,
    language_picker_kb,
    location_request_kb,
    main_menu_kb,
)
from states.order_states import OrderFlow
from utils import (
    update_user_state,
    update_user_tag,
    validate_address,
    validate_name,
    validate_phone,
)
from utils.i18n import t, get_user_language, set_user_language, LANGUAGES
from utils.security import is_admin_async

router = Router()


async def _cleanup_stale_drafts(session, user_id: int) -> None:
    """Delete any old draft orders for this user before starting a new flow.

    Prevents the bug where an old cart's items get mixed into a new order.
    """
    draft_orders = (
        await session.execute(
            select(Order).where(Order.user_id == user_id, Order.status == "draft")
        )
    ).scalars().all()
    for o in draft_orders:
        await session.delete(o)
    if draft_orders:
        await session.commit()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    tg_user = message.from_user
    async with async_session() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == tg_user.id)
            )
        ).scalar_one_or_none()

        is_new = False
        if user is None:
            is_new = True
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                tag="start_bosdi",
                language=None,
            )
            session.add(user)
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                user = (
                    await session.execute(
                        select(User).where(User.telegram_id == tg_user.id)
                    )
                ).scalar_one()
        else:
            if user.username != tg_user.username:
                await session.execute(
                    update(User).where(User.telegram_id == tg_user.id).values(
                        username=tg_user.username,
                    )
                )
                await session.commit()

        # If language not set -> ask language FIRST
        if is_new or not user.language:
            await state.set_state(OrderFlow.waiting_language)
            await update_user_state(session, tg_user.id, "OrderFlow:waiting_language")
            await message.answer(
                t("uz", "welcome_lang"),
                reply_markup=language_picker_kb(),
            )
            return

        lang = user.language or "uz"

        # If profile is incomplete -> start registration flow
        if not (user.full_name and user.phone):
            await state.set_state(OrderFlow.waiting_name)
            await update_user_state(session, tg_user.id, "OrderFlow:waiting_name")
            await message.answer(
                t(lang, "welcome_new"),
                reply_markup=hide_reply_kb(),
            )
            return

        # Already registered -> directly start category selection
        from handlers.user.order_flow import start_category_selection_message
        await start_category_selection_message(message, state)


@router.message(OrderFlow.waiting_name)
async def process_name(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    text = (message.text or "").strip()
    if not validate_name(text):
        await message.answer(
            t(lang, "name_invalid"),
            reply_markup=cancel_kb(lang),
        )
        return
    await state.update_data(full_name=text)
    await state.set_state(OrderFlow.waiting_phone)
    async with async_session() as session:
        await session.execute(
            update(User).where(User.telegram_id == message.from_user.id).values(
                full_name=text,
            )
        )
        await session.commit()
        await update_user_state(session, message.from_user.id, "OrderFlow:waiting_phone")
    await message.answer(
        t(lang, "ask_phone"),
        reply_markup=contact_request_kb(lang),
    )


@router.message(OrderFlow.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    """Handle 'send contact' button."""
    contact: Contact = message.contact
    if contact is None:
        return
    phone = validate_phone(contact.phone_number)
    lang = await get_user_language(message.from_user.id)
    if not phone:
        await message.answer(
            t(lang, "phone_invalid"),
            reply_markup=contact_request_kb(lang),
        )
        return
    await state.update_data(phone=phone)
    await _finalize_registration(message, state)


@router.message(OrderFlow.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    raw = (message.text or "").strip()
    normalized = validate_phone(raw)
    if not normalized:
        await message.answer(
            t(lang, "phone_invalid"),
            reply_markup=contact_request_kb(lang),
        )
        return
    await state.update_data(phone=normalized)
    await _finalize_registration(message, state)


async def _finalize_registration(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    async with async_session() as session:
        await session.execute(
            update(User).where(User.telegram_id == message.from_user.id).values(
                full_name=data.get("full_name"),
                phone=data.get("phone"),
                tag="kontakt_berdi",
            )
        )
        await session.commit()
        await update_user_tag(session, message.from_user.id, "kontakt_berdi")
        user = (
            await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        ).scalar_one_or_none()

    from utils.security import get_bot
    from services.notifications import notify_admin_user_registered
    bot = get_bot()
    if bot and user:
        await notify_admin_user_registered(bot, user)

    await state.clear()
    from handlers.user.order_flow import start_category_selection_message
    await start_category_selection_message(message, state)


# --- Main menu -------------------------------------------------------------

async def _send_main_menu(message: Message, user_id: int, name: str, lang: str):
    is_adm = await is_admin_async(user_id)
    text = t(lang, "welcome_back", name=name)
    await message.answer(text, reply_markup=main_menu_kb(is_admin=is_adm, lang=lang))


@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_language(callback.from_user.id)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, None)
    is_adm = await is_admin_async(callback.from_user.id)
    await callback.message.edit_text(
        t(lang, "welcome_back", name=callback.from_user.first_name or "Do'st"),
        reply_markup=main_menu_kb(is_admin=is_adm, lang=lang),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:new_order")
async def cb_new_order(callback: CallbackQuery, state: FSMContext):
    # Clean up stale drafts before starting fresh
    async with async_session() as session:
        from sqlalchemy import select as _sel
        user = (
            await session.execute(
                _sel(User).where(User.telegram_id == callback.from_user.id)
            )
        ).scalar_one_or_none()
        if user:
            await _cleanup_stale_drafts(session, user.id)
    from handlers.user.order_flow import start_category_selection
    await start_category_selection(callback, state)


@router.callback_query(F.data == "menu:my_orders")
async def cb_my_orders(callback: CallbackQuery, state: FSMContext):
    from handlers.user.my_orders import show_my_orders
    await show_my_orders(callback, state, page=0)


# --- Language picker ------------------------------------------------------

@router.callback_query(F.data == "menu:lang")
async def cb_lang_menu(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        t(lang, "lang_picker_title"),
        reply_markup=language_picker_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_lang(callback: CallbackQuery, state: FSMContext):
    try:
        _, code = callback.data.split(":")
    except ValueError:
        await callback.answer()
        return
    if code not in LANGUAGES:
        await callback.answer()
        return
    await set_user_language(callback.from_user.id, code)
    lang = code

    current_state = await state.get_state()
    async with async_session() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
        ).scalar_one_or_none()

    if current_state == OrderFlow.waiting_language or not (user and user.full_name and user.phone and user.address):
        await state.set_state(OrderFlow.waiting_name)
        async with async_session() as session:
            await update_user_state(session, callback.from_user.id, "OrderFlow:waiting_name")
        await callback.message.edit_text(t(lang, "welcome_new"))
        await callback.answer()
        return

    await callback.message.edit_text(t(code, "lang_set"))
    await callback.answer()
    from handlers.user.order_flow import start_category_selection
    await start_category_selection(callback, state)


# --- Global cancel --------------------------------------------------------

@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.clear()
    async with async_session() as session:
        await session.execute(
            update(User).where(User.telegram_id == callback.from_user.id).values(
                tag="bekor_qildi",
                current_state=None,
            )
        )
        await session.commit()
    is_adm = await is_admin_async(callback.from_user.id)
    if callback.message and callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            t(lang, "cancelled"),
            reply_markup=main_menu_kb(is_admin=is_adm, lang=lang),
        )
    else:
        await callback.message.edit_text(
            t(lang, "cancelled"),
            reply_markup=main_menu_kb(is_admin=is_adm, lang=lang),
        )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await get_user_language(message.from_user.id)
    if lang == "ru":
        text = (
            "ℹ️ Помощь:\n\n"
            "/start — главное меню\n"
            "/orders — мои заказы\n"
            "/cancel — отменить текущий процесс\n"
            "/help — этот текст\n\n"
            f"Для оплаты и вопросов: @{ADMIN_USERNAME}"
        )
    elif lang == "en":
        text = (
            "ℹ️ Help:\n\n"
            "/start — main menu\n"
            "/orders — my orders\n"
            "/cancel — cancel current flow\n"
            "/help — this text\n\n"
            f"For payment and questions: @{ADMIN_USERNAME}"
        )
    else:
        text = (
            "ℹ️ Yordam:\n\n"
            "/start — bosh menyu\n"
            "/orders — mening buyurtmalarim\n"
            "/cancel — joriy jarayonni bekor qilish\n"
            "/help — shu yordam matni\n\n"
            f"To'lov va savollar uchun admin: @{ADMIN_USERNAME}"
        )
    await message.answer(text)


@router.message(Command("orders"))
async def cmd_orders(message: Message, state: FSMContext):
    from handlers.user.my_orders import show_my_orders_message
    await show_my_orders_message(message, state, page=0)
