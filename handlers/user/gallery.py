"""Gallery browsing: multi-photo album view (4 items per page) with auto-cleanup."""
from __future__ import annotations

import math
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto
from sqlalchemy import select

from database.db import async_session
from database.models import Category, Product
from keyboards.user_kb import gallery_album_kb
from states.order_states import OrderFlow
from utils import update_user_state
from utils.i18n import get_entity_name, get_user_language, t

router = Router()

PAGE_SIZE = 4


async def _get_products_for_category(session, category_id: int):
    res = await session.execute(
        select(Product)
        .where(Product.category_id == category_id, Product.is_active == True)  # noqa: E712
        .order_by(Product.order_index, Product.id)
    )
    return res.scalars().all()


async def clear_previous_gallery_messages(bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    prev_msg_ids = data.get("last_gallery_msg_ids", [])
    if prev_msg_ids:
        for mid in prev_msg_ids:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass
        await state.update_data(last_gallery_msg_ids=[])


async def show_gallery_page(callback: CallbackQuery, state: FSMContext, page: int):
    lang = await get_user_language(callback.from_user.id)
    data = await state.get_data()
    category_id = data.get("category_id")
    if category_id is None:
        await callback.answer("Kategoriya topilmadi.", show_alert=True)
        return

    async with async_session() as session:
        products = await _get_products_for_category(session, category_id)
        cat = await session.get(Category, category_id)
        cat_name = await get_entity_name(cat, lang) if cat else "Katalog"

    if not products:
        await callback.message.edit_text(t(lang, "gallery_empty"))
        await callback.answer()
        return

    total_pages = math.ceil(len(products) / PAGE_SIZE)
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * PAGE_SIZE
    page_products = products[start_idx : start_idx + PAGE_SIZE]

    bot = callback.bot
    chat_id = callback.from_user.id

    # Clean up previous 4-photo album & menu messages
    await clear_previous_gallery_messages(bot, chat_id, state)
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    media_group = []
    page_items = []
    for idx, p in enumerate(page_products, start=start_idx + 1):
        pname = await get_entity_name(p, lang)
        cap = f"🖼 #{idx} Kartinka ({cat_name})\n{pname or ''}".strip()
        media_group.append(InputMediaPhoto(media=p.photo_file_id, caption=cap))
        page_items.append((p.id, idx, pname or f"Kartinka #{idx}"))

    new_msg_ids = []
    try:
        sent_photos = await bot.send_media_group(chat_id=chat_id, media=media_group)
        for m in sent_photos:
            new_msg_ids.append(m.message_id)
    except Exception:
        for p_idx, p in enumerate(page_products, start=start_idx + 1):
            pname = await get_entity_name(p, lang)
            cap = f"🖼 #{p_idx} Kartinka ({cat_name})\n{pname or ''}".strip()
            try:
                sm = await bot.send_photo(chat_id=chat_id, photo=p.photo_file_id, caption=cap)
                new_msg_ids.append(sm.message_id)
            except Exception:
                pass

    kb = gallery_album_kb(page_items, page, total_pages, lang)
    menu_msg = await bot.send_message(
        chat_id=chat_id,
        text=f"👇 <b>{cat_name}</b> bo'limidan tanlamoqchi bo'lgan kartinangizni tanlang:",
        reply_markup=kb,
    )
    new_msg_ids.append(menu_msg.message_id)

    await state.update_data(current_gallery_page=page, last_gallery_msg_ids=new_msg_ids)
    await callback.answer()


@router.callback_query(F.data.startswith("gpage:"))
async def cb_gallery_page(callback: CallbackQuery, state: FSMContext):
    try:
        _, page_str = callback.data.split(":")
        page = int(page_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await state.set_state(OrderFlow.browsing_gallery)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, "OrderFlow:browsing_gallery")
    await show_gallery_page(callback, state, page)


@router.callback_query(F.data.startswith("gsel:"))
async def cb_gallery_select(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        _, pid_str = callback.data.split(":")
        product_id = int(pid_str)
    except (ValueError, IndexError):
        return
    await state.update_data(current_product_id=product_id)

    # Clear gallery album photos before moving to material selection
    bot = callback.bot
    chat_id = callback.from_user.id
    await clear_previous_gallery_messages(bot, chat_id, state)

    from handlers.user.order_flow import start_material_selection
    await start_material_selection(callback, state, product_id)


@router.callback_query(F.data == "back:gallery")
async def cb_back_to_gallery(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("current_gallery_page", 0)
    await state.set_state(OrderFlow.browsing_gallery)
    async with async_session() as session:
        await update_user_state(session, callback.from_user.id, "OrderFlow:browsing_gallery")
    await show_gallery_page(callback, state, page)
