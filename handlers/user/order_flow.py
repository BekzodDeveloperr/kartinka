"""Core order flow: category -> gallery -> material -> size -> cart ->
deadline -> promo -> final confirm -> notify admin -> contact admin button."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select, update

from config import ADMIN_IDS
from database.db import async_session
from database.models import (
    Category,
    Material,
    Order,
    OrderItem,
    PaymentRequestLog,
    PriceMatrix,
    Product,
    PromoCode,
    PromoUsage,
    Size,
    User,
)
from keyboards.user_kb import (
    cart_view_kb,
    confirm_item_kb,
    deadline_kb,
    final_confirm_kb,
    materials_kb,
    more_items_kb,
    pay_request_kb,
    promo_kb,
    sizes_kb,
)
from services.notifications import (
    notify_admin_new_order,
    notify_admin_payment_request,
    notify_user_status_change,
)
from states.order_states import OrderFlow
from utils import (
    format_order_details,
    format_price,
    update_user_state,
    update_user_tag,
)
from utils.i18n import t, get_user_language, get_entity_name
from utils.security import get_bot

router = Router()


async def edit_or_send_text(callback: CallbackQuery, text: str, reply_markup=None):
    """Safely edit a message or send text message if previous message was deleted or a photo."""
    bot = callback.bot
    chat_id = callback.from_user.id
    if not callback.message:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
        return
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            await bot.send_message(chat_id, text, reply_markup=reply_markup)


# ---------------------------------------------------------------------------
# Category selection
# ---------------------------------------------------------------------------

async def start_category_selection(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(OrderFlow.choosing_category)
    async with async_session() as session:
        cats = (
            await session.execute(select(Category).order_by(Category.id))
        ).scalars().all()
        await update_user_state(session, callback.from_user.id, "OrderFlow:choosing_category")
    if not cats:
        await edit_or_send_text(
            callback,
            "Hozircha bo'limlar mavjud emas. Iltimos, adminga murojaat qiling."
        )
        await callback.answer()
        return
    cats_localized = [(c.id, await get_entity_name(c, lang)) for c in cats]
    from keyboards.user_kb import category_kb
    kb = category_kb(cats_localized, lang)
    await edit_or_send_text(callback, t(lang, "pick_category"), reply_markup=kb)
    await callback.answer()


async def start_category_selection_message(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    await state.set_state(OrderFlow.choosing_category)
    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        ).scalar_one_or_none()
        if user:
            from handlers.user.start import _cleanup_stale_drafts
            await _cleanup_stale_drafts(session, user.id)
        cats = (
            await session.execute(select(Category).order_by(Category.id))
        ).scalars().all()
        await update_user_state(session, message.from_user.id, "OrderFlow:choosing_category")
    if not cats:
        await message.answer(
            "Hozircha bo'limlar mavjud emas. Iltimos, adminga murojaat qiling."
        )
        return
    cats_localized = [(c.id, await get_entity_name(c, lang)) for c in cats]
    from keyboards.user_kb import category_kb
    kb = category_kb(cats_localized, lang)
    await message.answer(t(lang, "pick_category"), reply_markup=kb)


# Need to import after definition for cycle
from keyboards.user_kb import category_kb  # noqa: E402


@router.callback_query(F.data.startswith("cat:"))
async def cb_pick_category(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cat:restart":
        await start_category_selection(callback, state)
        return
    try:
        _, cid_str = callback.data.split(":")
        category_id = int(cid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await state.update_data(category_id=category_id)
    async with async_session() as session:
        await update_user_tag(session, callback.from_user.id, "turni_tanladi")
    await state.set_state(OrderFlow.browsing_gallery)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, "OrderFlow:browsing_gallery")
    from handlers.user.gallery import show_gallery_page
    await show_gallery_page(callback, state, 0)


@router.callback_query(F.data == "cat:restart")
async def cb_restart_category(callback: CallbackQuery, state: FSMContext):
    await start_category_selection(callback, state)


# ---------------------------------------------------------------------------
# Material selection
# ---------------------------------------------------------------------------

async def start_material_selection(callback: CallbackQuery, state: FSMContext, product_id: int):
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(OrderFlow.choosing_material)
    await state.update_data(current_product_id=product_id)
    async with async_session() as session:
        materials = (
            await session.execute(select(Material).order_by(Material.id))
        ).scalars().all()
        await update_user_state(session, callback.from_user.id, "OrderFlow:choosing_material")
    if not materials:
        await edit_or_send_text(callback, "Xomashyolar topilmadi.")
        try:
            await callback.answer()
        except Exception:
            pass
        return
    mats_loc = [(m.id, await get_entity_name(m, lang)) for m in materials]
    kb = materials_kb(mats_loc, lang)
    await edit_or_send_text(callback, t(lang, "pick_material"), reply_markup=kb)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("mat:"))
async def cb_pick_material(callback: CallbackQuery, state: FSMContext):
    try:
        _, mid_str = callback.data.split(":")
        material_id = int(mid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await state.update_data(current_material_id=material_id)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Size, PriceMatrix.price)
                .join(PriceMatrix, PriceMatrix.size_id == Size.id)
                .where(PriceMatrix.material_id == material_id)
                .order_by(Size.id)
            )
        ).all()
        await update_user_state(session, callback.from_user.id, "OrderFlow:choosing_size")
    if not rows:
        await edit_or_send_text(callback, "Bu xomashyo uchun razmerlar topilmadi.")
        await callback.answer()
        return
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(OrderFlow.choosing_size)
    from utils.formatting import format_price
    sizes_loc = [
        (s.id, await get_entity_name(s, lang), format_price(price))
        for s, price in rows
    ]
    kb = sizes_kb(sizes_loc, lang)
    await edit_or_send_text(callback, t(lang, "pick_size"), reply_markup=kb)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "back:material")
async def cb_back_to_material(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("current_product_id")
    await start_material_selection(callback, state, product_id)


# ---------------------------------------------------------------------------
# Size selection + price
# ---------------------------------------------------------------------------

import re


async def estimate_custom_size_price(material_id: int, custom_text: str, session) -> int:
    """Estimate price for custom size based on material rates in PriceMatrix."""
    numbers = [int(n) for n in re.findall(r'\d+', custom_text)]
    if len(numbers) >= 2:
        w, h = numbers[0], numbers[1]
        area = w * h
        rows = (
            await session.execute(
                select(Size.name_uz, PriceMatrix.price)
                .join(PriceMatrix, PriceMatrix.size_id == Size.id)
                .where(PriceMatrix.material_id == material_id)
            )
        ).all()
        best_rate = 35.0
        if rows:
            rates = []
            for sname, price in rows:
                sn = [int(n) for n in re.findall(r'\d+', sname or '')]
                if len(sn) >= 2 and (sn[0] * sn[1]) > 0:
                    rates.append(price / (sn[0] * sn[1]))
            if rates:
                best_rate = sum(rates) / len(rates)
        estimated = int(area * best_rate)
        return max(50000, round(estimated / 5000) * 5000)
    return 150000


@router.callback_query(F.data.startswith("size:"))
async def cb_pick_size(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer()
        return
    sid_str = parts[1]

    if sid_str == "custom":
        lang = await get_user_language(callback.from_user.id)
        await state.set_state(OrderFlow.waiting_custom_size)
        prompt = (
            "✍️ <b>Iltimos, o'zingiz xohlagan o'lchamni kiriting:</b>\n\n"
            "(Masalan: 70x110 cm yoki 120x150 cm)"
            if lang == "uz" else
            ("✍️ <b>Введите желаемый размер:</b>\n\n(Например: 70x110 см или 120x150 см)" if lang == "ru" else "✍️ <b>Enter your custom size:</b>\n\n(Example: 70x110 cm or 120x150 cm)")
        )
        await edit_or_send_text(callback, prompt, reply_markup=cancel_kb(lang))
        await callback.answer()
        return

    try:
        size_id = int(sid_str)
    except ValueError:
        await callback.answer()
        return

    lang = await get_user_language(callback.from_user.id)
    data = await state.get_data()
    material_id = data.get("current_material_id")
    product_id = data.get("current_product_id")
    async with async_session() as session:
        price_row = (
            await session.execute(
                select(PriceMatrix.price).where(
                    PriceMatrix.material_id == material_id,
                    PriceMatrix.size_id == size_id,
                )
            )
        ).scalar_one_or_none()
        if price_row is None:
            await callback.answer("Narx topilmadi.", show_alert=True)
            return
        product = await session.get(Product, product_id)
        material = await session.get(Material, material_id)
        size = await session.get(Size, size_id)

    await state.update_data(current_size_id=size_id, custom_size_text=None, current_price=price_row)
    await state.set_state(OrderFlow.confirming_item)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, "OrderFlow:confirming_item")
        await update_user_tag(session, callback.from_user.id, "narxni_kordi")

    pname = await get_entity_name(product, lang) if product else f"#{product_id}"
    mname = await get_entity_name(material, lang) if material else "-"
    sname = await get_entity_name(size, lang) if size else "-"

    text = (
        f"🖼 <b>Tanlangan mahsulot ma'lumotlari:</b>\n\n"
        f"🖼 <b>Mahsulot:</b> {pname}\n"
        f"🧵 <b>Matosi:</b> {mname}\n"
        f"📐 <b>O'lchami:</b> {sname}\n"
        f"💰 <b>Narxi:</b> <b>{format_price(price_row)} so'm</b>\n\n"
        f"Ushbu buyurtmani rasmiylashtiramizmi?"
    )
    await edit_or_send_text(callback, text, reply_markup=confirm_item_kb(lang))
    await callback.answer()


@router.message(OrderFlow.waiting_custom_size, F.text)
async def process_custom_size_input(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    text = (message.text or "").strip()
    if not text or len(text) < 2:
        await message.answer("❌ Noto'g'ri o'lcham format kiritildi. Qaytadan kiriting:")
        return

    data = await state.get_data()
    material_id = data.get("current_material_id")
    product_id = data.get("current_product_id")

    async with async_session() as session:
        estimated_price = await estimate_custom_size_price(material_id, text, session)
        product = await session.get(Product, product_id)
        material = await session.get(Material, material_id)

    await state.update_data(
        current_size_id=None,
        custom_size_text=text,
        current_price=estimated_price,
    )
    await state.set_state(OrderFlow.confirming_item)
    async with async_session() as session:
        await update_user_state(session, message.from_user.id, "OrderFlow:confirming_item")
        await update_user_tag(session, message.from_user.id, "narxni_kordi")

    pname = await get_entity_name(product, lang) if product else f"#{product_id}"
    mname = await get_entity_name(material, lang) if material else "-"

    summary_text = (
        f"🖼 <b>Tanlangan mahsulot ma'lumotlari:</b>\n\n"
        f"🖼 <b>Mahsulot:</b> {pname}\n"
        f"🧵 <b>Matosi:</b> {mname}\n"
        f"📐 <b>O'lchami:</b> {text} (Maxsus)\n"
        f"💰 <b>Mo'ljallangan narxi:</b> <b>{format_price(estimated_price)} so'm</b>\n\n"
        f"Ushbu buyurtmani rasmiylashtiramizmi?"
    )
    await message.answer(summary_text, reply_markup=confirm_item_kb(lang))


@router.callback_query(F.data == "cart:redo", OrderFlow.confirming_item)
async def cb_cart_redo(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("current_product_id")
    await start_material_selection(callback, state, product_id)


async def _ensure_item_in_draft(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("current_product_id")
    material_id = data.get("current_material_id")
    size_id = data.get("current_size_id")
    custom_size_text = data.get("custom_size_text")
    price = data.get("current_price")
    if not (product_id and material_id and (size_id or custom_size_text) and price is not None):
        return
    async with async_session() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
        ).scalar_one_or_none()
        if user is None:
            return
        draft = (
            await session.execute(
                select(Order).where(Order.user_id == user.id, Order.status == "draft")
            )
        ).scalar_one_or_none()
        if draft is None:
            draft = Order(
                order_number=f"DRAFT-{user.id}",
                user_id=user.id,
                status="draft",
                total_price=0,
            )
            session.add(draft)
            await session.flush()
        existing_item = (
            await session.execute(
                select(OrderItem).where(
                    OrderItem.order_id == draft.id,
                    OrderItem.product_id == product_id,
                    OrderItem.material_id == material_id,
                    OrderItem.size_id == size_id,
                    OrderItem.custom_size == custom_size_text,
                )
            )
        ).scalar_one_or_none()
        if not existing_item:
            item = OrderItem(
                order_id=draft.id,
                product_id=product_id,
                material_id=material_id,
                size_id=size_id,
                custom_size=custom_size_text,
                price=price,
            )
            session.add(item)
            draft.total_price = (draft.total_price or 0) + price
            await session.commit()
            await update_user_tag(session, callback.from_user.id, "mahsulot_tanladi")
        await state.update_data(
            draft_order_id=draft.id,
            current_product_id=None,
            current_material_id=None,
            current_size_id=None,
            custom_size_text=None,
            current_price=None,
        )


@router.callback_query(F.data == "cart:more")
async def cb_cart_more(callback: CallbackQuery, state: FSMContext):
    await _ensure_item_in_draft(callback, state)
    await start_category_selection(callback, state)


@router.callback_query(F.data == "cart:done")
async def cb_cart_done(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await _ensure_item_in_draft(callback, state)
    await state.set_state(OrderFlow.choosing_deadline)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, "OrderFlow:choosing_deadline")
    await edit_or_send_text(callback, t(lang, "pick_deadline"), reply_markup=deadline_kb(lang))
    await callback.answer()


# ---------------------------------------------------------------------------
# Deadline -> promo
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("dl:"), OrderFlow.choosing_deadline)
async def cb_pick_deadline(callback: CallbackQuery, state: FSMContext):
    try:
        _, code = callback.data.split(":")
    except ValueError:
        await callback.answer()
        return
    await state.update_data(deadline_type=code)
    lang = await get_user_language(callback.from_user.id)
    await _proceed_to_final(callback, state, lang)


@router.message(OrderFlow.waiting_promo_code)
async def process_promo_code(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    raw = (message.text or "").strip().upper()
    if not raw or raw == "-":
        await state.update_data(promo_code=None, discount=0)
        await _proceed_to_final_message(message, state, lang)
        return

    async with async_session() as session:
        promo = (
            await session.execute(
                select(PromoCode).where(PromoCode.code == raw, PromoCode.is_active == True)  # noqa: E712
            )
        ).scalar_one_or_none()
        if promo is None:
            from keyboards.user_kb import cancel_kb
            await message.answer(t(lang, "promo_invalid"), reply_markup=cancel_kb(lang))
            return
        # Check validity
        now = datetime.now(timezone.utc)
        if promo.valid_until and promo.valid_until < now:
            from keyboards.user_kb import cancel_kb
            await message.answer(t(lang, "promo_invalid"), reply_markup=cancel_kb(lang))
            return
        if promo.max_uses > 0 and promo.uses_count >= promo.max_uses:
            from keyboards.user_kb import cancel_kb
            await message.answer(t(lang, "promo_invalid"), reply_markup=cancel_kb(lang))
            return
        # Check user hasn't used it
        user = (
            await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        ).scalar_one_or_none()
        if user is None:
            return
        existing = (
            await session.execute(
                select(PromoUsage).where(
                    PromoUsage.user_id == user.id, PromoUsage.promo_id == promo.id
                )
            )
        ).scalar_one_or_none()
        if existing:
            from keyboards.user_kb import cancel_kb
            await message.answer(t(lang, "promo_already_used"), reply_markup=cancel_kb(lang))
            return

        # Compute discount
        data = await state.get_data()
        draft_id = data.get("draft_order_id")
        draft = await session.get(Order, draft_id) if draft_id else None
        if draft is None:
            return
        if draft.total_price < promo.min_order_amount:
            from keyboards.user_kb import cancel_kb
            await message.answer(t(lang, "promo_invalid"), reply_markup=cancel_kb(lang))
            return
        if promo.discount_type == "percent":
            discount = int(draft.total_price * promo.discount_value / 100)
        else:
            discount = min(promo.discount_value, draft.total_price)

        await state.update_data(promo_code=promo.code, discount=discount, promo_id=promo.id)

    await _proceed_to_final_message(message, state, lang)


async def _proceed_to_final(callback: CallbackQuery, state: FSMContext, lang: str):
    """Render final confirmation for callback flow."""
    data = await state.get_data()
    draft_id = data.get("draft_order_id")
    async with async_session() as session:
        draft = await session.get(Order, draft_id) if draft_id else None
        if draft is None:
            await callback.answer("Savat topilmadi.", show_alert=True)
            return
        # Apply promo discount
        if data.get("discount"):
            draft.discount = data["discount"]
            draft.promo_code = data.get("promo_code")
            await session.commit()
            await session.refresh(draft)
        summary = await format_order_details(session, draft, lang)
    await state.set_state(OrderFlow.final_confirmation)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, "OrderFlow:final_confirmation")
    await edit_or_send_text(
        callback,
        summary + "\n\n" + ("Buyurtmani tasdiqlaysizmi?" if lang == "uz" else ("Подтверждаете заказ?" if lang == "ru" else "Confirm order?")),
        reply_markup=final_confirm_kb(lang),
    )
    await callback.answer()


async def _proceed_to_final_message(message: Message, state: FSMContext, lang: str):
    """Render final confirmation for message flow (after promo input)."""
    data = await state.get_data()
    draft_id = data.get("draft_order_id")
    async with async_session() as session:
        draft = await session.get(Order, draft_id) if draft_id else None
        if draft is None:
            await message.answer("Savat topilmadi.")
            return
        if data.get("discount"):
            draft.discount = data["discount"]
            draft.promo_code = data.get("promo_code")
            await session.commit()
            await session.refresh(draft)
        summary = await format_order_details(session, draft, lang)
    await state.set_state(OrderFlow.final_confirmation)
    async with async_session() as session:
        await update_user_state(session, message.from_user.id, "OrderFlow:final_confirmation")

    extra = ""
    if data.get("discount"):
        extra = "\n" + t(lang, "promo_applied", discount=format_price(data["discount"]))
    await message.answer(
        summary + extra + "\n\n" + ("Buyurtmani tasdiqlaysizmi?" if lang == "uz" else ("Подтверждаете заказ?" if lang == "ru" else "Confirm order?")),
        reply_markup=final_confirm_kb(lang),
    )


# ---------------------------------------------------------------------------
# Final confirm
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "fin:confirm", OrderFlow.final_confirmation)
async def cb_final_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_user_language(callback.from_user.id)
    data = await state.get_data()
    draft_id = data.get("draft_order_id")
    deadline = data.get("deadline_type", "standard")
    discount = data.get("discount", 0)
    promo_code = data.get("promo_code")
    promo_id = data.get("promo_id")
    if not draft_id:
        await callback.answer("Savat topilmadi.", show_alert=True)
        return

    async with async_session() as session:
        draft = await session.get(Order, draft_id)
        if draft is None or draft.status != "draft":
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        draft.status = "yangi"
        draft.order_number = f"{draft.id:06d}"
        draft.deadline_type = deadline
        draft.discount = discount
        draft.promo_code = promo_code
        draft.finalized_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(draft)
        user = await session.get(User, draft.user_id)
        await update_user_tag(session, callback.from_user.id, "buyurtma_berdi")

        # Increment promo usage if applicable
        if promo_id:
            promo = await session.get(PromoCode, promo_id)
            if promo:
                promo.uses_count = (promo.uses_count or 0) + 1
                session.add(PromoUsage(
                    promo_id=promo.id,
                    user_id=user.id,
                    order_id=draft.id,
                ))
            await session.commit()

        summary = await format_order_details(session, draft, lang)

    # Notify admin (real-time)
    await notify_admin_new_order(bot, summary, callback.from_user.id, draft.id)

    await state.clear()
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, None)

    from utils.security import get_admin_username_async
    admin_username = await get_admin_username_async()

    await edit_or_send_text(
        callback,
        t(lang, "order_placed", num=draft.order_number),
        reply_markup=pay_request_kb(draft.id, draft.order_number, admin_username, callback.from_user.id, lang),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# "Admin bilan bog'lanish" — auto message to admin (with spam protection)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay:req:"))
async def cb_pay_request(callback: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_user_language(callback.from_user.id)
    try:
        _, _, oid_str = callback.data.split(":")
        order_id = int(oid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return

    # Spam protection: check last request for this order
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order is None:
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        user = await session.get(User, order.user_id)
        if user is None:
            await callback.answer()
            return
        # Check cooldown (5 min default)
        last_req = (
            await session.execute(
                select(PaymentRequestLog)
                .where(PaymentRequestLog.order_id == order_id)
                .order_by(PaymentRequestLog.requested_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        cooldown_min = 5
        from database.models import BotSetting
        cd_setting = await session.get(BotSetting, "notify_payment_request_cooldown_min")
        if cd_setting:
            try:
                cooldown_min = int(cd_setting.value)
            except Exception:
                pass
        if last_req:
            # Handle both tz-aware and tz-naive datetimes (SQLite drops tzinfo)
            now_utc = datetime.now(timezone.utc)
            last_time = last_req.requested_at
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            if (now_utc - last_time) < timedelta(minutes=cooldown_min):
                await callback.answer(t(lang, "pay_request_cooldown"), show_alert=True)
                return

        # Log this request
        session.add(PaymentRequestLog(
            order_id=order_id,
            user_id=user.id,
        ))
        await session.commit()

    # Send auto-message to all admins
    await notify_admin_payment_request(bot, order=order, user=user)

    await callback.message.answer(
        t(lang, "pay_request_sent", tg_id=callback.from_user.id, num=order.order_number),
    )
    await callback.answer("✅")


# ---------------------------------------------------------------------------
# Review request — when order becomes 'yetkazildi'
# ---------------------------------------------------------------------------

async def send_review_request(bot: Bot, order: Order, lang: str = "uz") -> None:
    """Send a 1-5 star review request to the customer after delivery."""
    from keyboards.user_kb import review_kb
    try:
        await bot.send_message(
            order.user.telegram_id if hasattr(order, 'user') and order.user else None,
            t(lang, "review_ask", num=order.order_number),
            reply_markup=review_kb(order.id, lang),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("review:"))
async def cb_review(callback: CallbackQuery, state: FSMContext):
    """Handle 1-5 star rating clicks. Format: review:<order_id>:<rating> OR review:skip:<order_id>"""
    from database.models import Review
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, op, payload = parts
    if op == "skip":
        await callback.message.edit_text(t(lang, "review_thanks"))
        await callback.answer()
        return
    # op == order_id, payload == rating
    try:
        order_id = int(op)
        rating = int(payload)
    except ValueError:
        await callback.answer()
        return
    if rating < 1 or rating > 5:
        await callback.answer()
        return
    async with async_session() as session:
        # Check if review already exists
        existing = (
            await session.execute(
                select(Review).where(Review.order_id == order_id)
            )
        ).scalar_one_or_none()
        if existing:
            await callback.answer(t(lang, "review_already"), show_alert=True)
            return
        order = await session.get(Order, order_id)
        if order is None:
            await callback.answer()
            return
        user = await session.get(User, order.user_id)
        if user is None or user.telegram_id != callback.from_user.id:
            await callback.answer()
            return
        # Save review (comment later)
        review = Review(
            order_id=order_id,
            user_id=user.id,
            rating=rating,
            comment=None,
        )
        session.add(review)
        await session.commit()
    # Ask for optional comment
    await state.set_state(OrderFlow.leaving_review)
    await state.update_data(review_id=review.id, review_order_id=order_id)
    await callback.message.edit_text(t(lang, "review_ask_comment"))
    await callback.answer()


@router.message(OrderFlow.leaving_review)
async def process_review_comment(message: Message, state: FSMContext):
    from database.models import Review
    lang = await get_user_language(message.from_user.id)
    text = (message.text or "").strip()
    data = await state.get_data()
    review_id = data.get("review_id")
    await state.clear()
    if not review_id:
        return
    async with async_session() as session:
        review = await session.get(Review, review_id)
        if review and text and text != "-":
            review.comment = text
            await session.commit()
    await message.answer(t(lang, "review_thanks"))
