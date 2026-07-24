"""Catalog management: categories, products, materials, sizes, prices.
Features:
  - Multilingual names (uz/ru/en)
  - Confirm-before-delete
  - Order_index reordering for products
  - Toggle product is_active
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from database.db import async_session
from database.models import Category, Material, PriceMatrix, Product, Size
from keyboards.admin_kb import (
    admin_back_kb,
    admin_catalog_menu_kb,
    admin_confirm_delete_kb,
)
from states.order_states import AdminFlow
from utils.security import IsAdminFilter, get_admin_role_async, role_has_permission

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


async def _check_perm(telegram_id: int) -> bool:
    role = await get_admin_role_async(telegram_id)
    return role_has_permission(role, "catalog")


# ------------------- Menu -------------------

@router.callback_query(F.data == "admin:catalog")
async def cb_catalog_menu(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await callback.message.edit_text(
        "🛠 <b>Katalog boshqaruvi</b>",
        reply_markup=admin_catalog_menu_kb(),
    )
    await callback.answer()


# ------------------- Categories -------------------

@router.callback_query(F.data == "cat_admin:categories")
async def cb_list_categories(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        rows = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for c in rows:
        b.button(text=f"🏷 {c.name_uz}", callback_data=f"catview:{c.id}")
    b.button(text="➕ Yangi kategoriya qo'shish", callback_data="catadd")
    b.button(text="⬅️ Katalog", callback_data="admin:catalog")
    b.adjust(1)
    text = "🏷 <b>Kategoriyalar ro'yxati:</b>\n\n" + ("\n".join(f"• {c.name_uz} (ID: #{c.id})" for c in rows) if rows else "*(Kategoriyalar mavjud emas)*")
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("catview:"))
async def cb_cat_view(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, cid_str = callback.data.split(":")
        cid = int(cid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        c = await session.get(Category, cid)
    if not c:
        await callback.answer("Kategoriya topilmadi.", show_alert=True)
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Nomini o'zgartirish", callback_data=f"catedit:{c.id}")
    b.button(text="🗑 Kategoriyani o'chirish", callback_data=f"catdel:{c.id}")
    b.button(text="⬅️ Kategoriyalar", callback_data="cat_admin:categories")
    b.adjust(1)
    await callback.message.edit_text(
        f"🏷 <b>Kategoriya:</b> {c.name_uz} (ID: #{c.id})\n\n"
        f"Quyidagi harakatlardan birini tanlang:",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("catedit:"))
async def cb_cat_edit_prompt(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, cid_str = callback.data.split(":")
        cid = int(cid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        c = await session.get(Category, cid)
    if not c:
        await callback.answer("Kategoriya topilmadi.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="edit_category", edit_category_id=cid)
    await callback.message.edit_text(
        f"✏️ <b>«{c.name_uz}»</b> kategoriyasi uchun yangi nom kiriting:",
        reply_markup=admin_back_kb("cat_admin:categories"),
    )
    await callback.answer()


@router.callback_query(F.data == "catadd")
async def cb_cat_add(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="add_category")
    await callback.message.edit_text(
        "✏️ Yangi kategoriya nomini kiriting:",
        reply_markup=admin_back_kb("cat_admin:categories"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("catdel:"))
async def cb_cat_del_prompt(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, cid_str = callback.data.split(":")
        cid = int(cid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await callback.message.edit_text(
        "❓ Kategoriyani o'chirishni tasdiqlaysizmi? "
        "Uning ostidagi barcha mahsulotlar ham o'chiriladi!",
        reply_markup=admin_confirm_delete_kb("category", cid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:category:"))
async def cb_cat_del_confirm(callback: CallbackQuery):
    try:
        _, _, _, cid_str = callback.data.split(":")
        cid = int(cid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        c = await session.get(Category, cid)
        if c:
            await session.delete(c)
            await session.commit()
    await cb_list_categories(callback)


@router.callback_query(F.data.startswith("cancel_del:category:"))
async def cb_cat_del_cancel(callback: CallbackQuery):
    await cb_list_categories(callback)


# ------------------- Materials -------------------

@router.callback_query(F.data == "cat_admin:materials")
async def cb_list_materials(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        rows = (await session.execute(select(Material).order_by(Material.id))).scalars().all()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for m in rows:
        b.button(text=f"🧵 {m.name_uz}", callback_data=f"matview:{m.id}")
    b.button(text="➕ Yangi xomashyo", callback_data="matadd")
    b.button(text="⬅️ Katalog", callback_data="admin:catalog")
    b.adjust(1)
    text = "🧵 <b>Xomashyolar (Materiallar):</b>\n\n" + ("\n".join(f"• {m.name_uz} (ID: #{m.id})" for m in rows) if rows else "*(Materiallar mavjud emas)*")
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("matview:"))
async def cb_mat_view(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, mid_str = callback.data.split(":")
        mid = int(mid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        m = await session.get(Material, mid)
    if not m:
        await callback.answer("Material topilmadi.", show_alert=True)
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Nomini o'zgartirish", callback_data=f"matedit:{m.id}")
    b.button(text="🗑 Materialni o'chirish", callback_data=f"matdel:{m.id}")
    b.button(text="⬅️ Materiallar", callback_data="cat_admin:materials")
    b.adjust(1)
    await callback.message.edit_text(
        f"🧵 <b>Material:</b> {m.name_uz} (ID: #{m.id})\n\n"
        f"Quyidagi harakatlardan birini tanlang:",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("matedit:"))
async def cb_mat_edit_prompt(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, mid_str = callback.data.split(":")
        mid = int(mid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        m = await session.get(Material, mid)
    if not m:
        await callback.answer("Material topilmadi.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="edit_material", edit_material_id=mid)
    await callback.message.edit_text(
        f"✏️ <b>«{m.name_uz}»</b> materialining yangi nomini kiriting:",
        reply_markup=admin_back_kb("cat_admin:materials"),
    )
    await callback.answer()


@router.callback_query(F.data == "matadd")
async def cb_mat_add(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="add_material")
    await callback.message.edit_text(
        "✏️ Yangi xomashyo nomini kiriting:",
        reply_markup=admin_back_kb("cat_admin:materials"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("matdel:"))
async def cb_mat_del_prompt(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, mid_str = callback.data.split(":")
        mid = int(mid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await callback.message.edit_text(
        "❓ Xomashyoni o'chirishni tasdiqlaysizmi?",
        reply_markup=admin_confirm_delete_kb("material", mid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:material:"))
async def cb_mat_del_confirm(callback: CallbackQuery):
    try:
        _, _, _, mid_str = callback.data.split(":")
        mid = int(mid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        m = await session.get(Material, mid)
        if m:
            await session.delete(m)
            await session.commit()
    await cb_list_materials(callback)


@router.callback_query(F.data.startswith("cancel_del:material:"))
async def cb_mat_del_cancel(callback: CallbackQuery):
    await cb_list_materials(callback)


# ------------------- Sizes -------------------

@router.callback_query(F.data == "cat_admin:sizes")
async def cb_list_sizes(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        rows = (await session.execute(select(Size).order_by(Size.id))).scalars().all()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for s in rows:
        b.button(text=f"📐 {s.name_uz}", callback_data=f"sizeview:{s.id}")
    b.button(text="➕ Yangi razmer", callback_data="sizeadd")
    b.button(text="⬅️ Katalog", callback_data="admin:catalog")
    b.adjust(1)
    text = "📐 <b>O'lchamlar (Razmerlar):</b>\n\n" + ("\n".join(f"• {s.name_uz} (ID: #{s.id})" for s in rows) if rows else "*(Razmerlar mavjud emas)*")
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("sizeview:"))
async def cb_size_view(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, sid_str = callback.data.split(":")
        sid = int(sid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        s = await session.get(Size, sid)
    if not s:
        await callback.answer("Razmer topilmadi.", show_alert=True)
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Nomini o'zgartirish", callback_data=f"sizedit:{s.id}")
    b.button(text="🗑 Razmerni o'chirish", callback_data=f"sizedel:{s.id}")
    b.button(text="⬅️ Razmerlar", callback_data="cat_admin:sizes")
    b.adjust(1)
    await callback.message.edit_text(
        f"📐 <b>O'lcham:</b> {s.name_uz} (ID: #{s.id})\n\n"
        f"Quyidagi harakatlardan birini tanlang:",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sizedit:"))
async def cb_size_edit_prompt(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, sid_str = callback.data.split(":")
        sid = int(sid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        s = await session.get(Size, sid)
    if not s:
        await callback.answer("Razmer topilmadi.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="edit_size", edit_size_id=sid)
    await callback.message.edit_text(
        f"✏️ <b>«{s.name_uz}»</b> razmerining yangi nomini kiriting:",
        reply_markup=admin_back_kb("cat_admin:sizes"),
    )
    await callback.answer()


@router.callback_query(F.data == "sizeadd")
async def cb_size_add(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="add_size")
    await callback.message.edit_text(
        "✏️ Yangi razmer nomini kiriting (masalan: 100x150):",
        reply_markup=admin_back_kb("cat_admin:sizes"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sizedel:"))
async def cb_size_del_prompt(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, sid_str = callback.data.split(":")
        sid = int(sid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await callback.message.edit_text(
        "❓ Razmerni o'chirishni tasdiqlaysizmi?",
        reply_markup=admin_confirm_delete_kb("size", sid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:size:"))
async def cb_size_del_confirm(callback: CallbackQuery):
    try:
        _, _, _, sid_str = callback.data.split(":")
        sid = int(sid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        s = await session.get(Size, sid)
        if s:
            await session.delete(s)
            await session.commit()
    await cb_list_sizes(callback)


@router.callback_query(F.data.startswith("cancel_del:size:"))
async def cb_size_del_cancel(callback: CallbackQuery):
    await cb_list_sizes(callback)


# ------------------- Products -------------------

@router.callback_query(F.data == "cat_admin:products")
async def cb_list_products(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Product, Category)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .order_by(Product.order_index, Product.id)
            )
        ).all()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for p, c in rows:
        active = "✅" if p.is_active else "❌"
        b.button(text=f"{active} #{p.id} {p.caption_uz or ''[:30]}", callback_data=f"prodopen:{p.id}")
    b.button(text="➕ Mahsulot (rasm) qo'shish", callback_data="prodadd")
    b.button(text="⬅️ Katalog", callback_data="admin:catalog")
    b.adjust(1)
    text = "🖼 Mahsulotlar:\n\n" + "\n".join(
        f"• #{p.id} | {p.caption_uz or '-'} | cat={c.name_uz if c else '-'} | {'✅' if p.is_active else '❌'}"
        for p, c in rows
    ) or "(bo'sh)"
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("prodopen:"))
async def cb_prod_open(callback: CallbackQuery):
    """Show product details with reorder / toggle / delete / edit caption buttons."""
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p is None:
            await callback.answer("Topilmadi.", show_alert=True)
            return
        c = await session.get(Category, p.category_id) if p.category_id else None
        text = (
            f"🖼 <b>Mahsulot #{p.id}</b>\n\n"
            f"📝 Nomi (caption uz): {p.caption_uz or '(bo\'sh)'}\n"
            f"📝 Caption (ru): {p.caption_ru or '-'}\n"
            f"📝 Caption (en): {p.caption_en or '-'}\n"
            f"🏷 Kategoriya: {c.name_uz if c else '-'}\n"
            f"📊 Tartib (order_index): {p.order_index}\n"
            f"{'✅ Faol' if p.is_active else '❌ Nofaol'}"
        )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Nomini (caption) tahrirlash", callback_data=f"prodeditcap:{pid}")
    b.button(text="⬆️ Yuqoriga", callback_data=f"produp:{pid}")
    b.button(text="⬇️ Pastga", callback_data=f"proddown:{pid}")
    b.button(text=f"{'🚫 Nofaol qilish' if p.is_active else '✅ Faol qilish'}", callback_data=f"prodtoggle:{pid}")
    b.button(text="🗑 O'chirish", callback_data=f"proddel:{pid}")
    b.button(text="⬅️ Mahsulotlar", callback_data="cat_admin:products")
    b.adjust(1, 2, 1, 1, 1)
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("prodeditcap:"))
async def cb_prod_edit_caption_start(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p is None:
            await callback.answer("Topilmadi.", show_alert=True)
            return
        curr_cap = p.caption_uz or "(bo'sh)"
    await state.set_state(AdminFlow.waiting_edit_caption)
    await state.update_data(edit_product_id=pid)
    await callback.message.edit_text(
        f"✏️ <b>Mahsulot #{pid} uchun yangi nom (caption) yuboring:</b>\n\n"
        f"Joriy nom: {curr_cap}\n\n"
        f"(Nomni o'chirish uchun '-' deb yuboring)",
        reply_markup=admin_back_kb(f"prodopen:{pid}"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_edit_caption)
async def cb_prod_edit_caption_save(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "-":
        text = ""
    data = await state.get_data()
    pid = data.get("edit_product_id")
    if not pid:
        await state.clear()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p:
            p.caption_uz = text
            await session.commit()
    await state.clear()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="👁 Mahsulotni ko'rish", callback_data=f"prodopen:{pid}")
    b.button(text="⬅️ Mahsulotlar ro'yxati", callback_data="cat_admin:products")
    b.adjust(1)
    await message.answer(
        f"✅ <b>Mahsulot #{pid} nomi yangilandi!</b>",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data.startswith("produp:"))
async def cb_prod_up(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p is None:
            return
        p.order_index = (p.order_index or 0) - 1
        await session.commit()
    await cb_prod_open(callback)


@router.callback_query(F.data.startswith("proddown:"))
async def cb_prod_down(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p is None:
            return
        p.order_index = (p.order_index or 0) + 1
        await session.commit()
    await cb_prod_open(callback)


@router.callback_query(F.data.startswith("prodtoggle:"))
async def cb_prod_toggle(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p is None:
            return
        p.is_active = not p.is_active
        await session.commit()
    await cb_prod_open(callback)


@router.callback_query(F.data == "prodadd")
async def cb_prod_add(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        cats = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    if not cats:
        await callback.answer("Avval kategoriya qo'shing.", show_alert=True)
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=c.name_uz, callback_data=f"prodcat:{c.id}")
    b.button(text="⬅️ Katalog", callback_data="admin:catalog")
    b.adjust(1)
    await state.set_state(AdminFlow.waiting_product_category)
    await state.update_data(admin_action="add_product_step1")
    await callback.message.edit_text(
        "🖼 Yangi mahsulotlar qo'shish. Avval kategoriyani tanlang:",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prodcat:"), AdminFlow.waiting_product_category)
async def cb_prod_pick_cat(callback: CallbackQuery, state: FSMContext):
    try:
        _, cid_str = callback.data.split(":")
        cid = int(cid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await state.update_data(new_product_category_id=cid, added_count=0)
    await state.set_state(AdminFlow.waiting_product_photo)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yakunlash", callback_data="prod_upload_done")
    b.button(text="⬅️ Bekor qilish", callback_data="cat_admin:products")
    b.adjust(1)

    await callback.message.edit_text(
        "📸 <b>Mahsulot rasmlarini yuboring:</b>\n\n"
        "Siz 1 ta yoki bir vaqtning o'zida bir nechta (10-20 ta) rasmlarni (albom ko'rinishida) yuborishingiz mumkin!\n"
        "Har bir rasm avtomatik mahsulot sifatida saqlanadi va keyinchalik nomini tahrirlashingiz mumkin.\n\n"
        "<i>Rasmlarni yuborib bo'lgach, pastdagi «✅ Yakunlash» tugmasini bosing.</i>",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_product_photo, F.photo)
async def cb_prod_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    caption = (message.caption or "").strip()

    data = await state.get_data()
    cid = data.get("new_product_category_id")
    added_count = data.get("added_count", 0)

    if not cid:
        await message.answer("Kategoriya topilmadi. Avval kategoriyani tanlang.")
        await state.clear()
        return

    async with async_session() as session:
        max_idx = (
            await session.execute(
                select(func.max(Product.order_index)).where(Product.category_id == cid)
            )
        ).scalar_one()
        p = Product(
            category_id=cid,
            photo_file_id=file_id,
            caption_uz=caption,
            order_index=(max_idx or 0) + 1,
            is_active=True,
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)

    new_count = added_count + 1
    await state.update_data(added_count=new_count)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yakunlash", callback_data="prod_upload_done")
    b.adjust(1)

    await message.answer(
        f"✅ <b>Rasm #{p.id} saqlandi!</b> (Jami qo'shildi: <b>{new_count}</b> ta)\n"
        f"Yana rasmlar yuborishingiz mumkin yoki yuborib bo'lgach «✅ Yakunlash»ni bosing.",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data == "prod_upload_done", AdminFlow.waiting_product_photo)
async def cb_prod_upload_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cnt = data.get("added_count", 0)
    await state.clear()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="🖼 Mahsulotlar ro'yxatiga o'tish", callback_data="cat_admin:products")
    b.adjust(1)
    await callback.message.edit_text(
        f"🎉 <b>Muvaffaqiyatli yakunlandi!</b>\n\n"
        f"Jami <b>{cnt}</b> ta yangi mahsulot bazaga qo'shildi.\n"
        f"Katalog ro'yxatidan ularga kirib, nomlarini (caption) istalgancha tahrirlashingiz mumkin.",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("proddel:"))
async def cb_prod_del_prompt(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await callback.message.edit_text(
        "❓ Mahsulotni o'chirishni tasdiqlaysizmi?",
        reply_markup=admin_confirm_delete_kb("product", pid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:product:"))
async def cb_prod_del_confirm(callback: CallbackQuery):
    try:
        _, _, _, pid_str = callback.data.split(":")
        pid = int(pid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        p = await session.get(Product, pid)
        if p:
            await session.delete(p)
            await session.commit()
    await cb_list_products(callback)


@router.callback_query(F.data.startswith("cancel_del:product:"))
async def cb_prod_del_cancel(callback: CallbackQuery):
    await cb_list_products(callback)


# ------------------- Prices -------------------

@router.callback_query(F.data == "cat_admin:prices")
async def cb_list_prices(callback: CallbackQuery):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        rows = (
            await session.execute(
                select(PriceMatrix, Material, Size)
                .join(Material, PriceMatrix.material_id == Material.id)
                .join(Size, PriceMatrix.size_id == Size.id)
                .order_by(Material.id, Size.id)
            )
        ).all()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for pm, m, s in rows:
        price_str = f"{pm.price:,}".replace(",", " ")
        b.button(
            text=f"✏️ {m.name_uz} / {s.name_uz} = {price_str}",
            callback_data=f"priceedit:{pm.material_id}:{pm.size_id}",
        )
    b.button(text="⬅️ Katalog", callback_data="admin:catalog")
    b.adjust(1)
    text_lines = ["💲 Narxlar matritsasi:", ""]
    for pm, m, s in rows:
        price_str = f"{pm.price:,}".replace(",", " ")
        text_lines.append(f"• {m.name_uz} / {s.name_uz} = {price_str} so'm")
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("priceedit:"))
async def cb_price_edit(callback: CallbackQuery, state: FSMContext):
    if not await _check_perm(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, mid_str, sid_str = callback.data.split(":")
        mid, sid = int(mid_str), int(sid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    await state.set_state(AdminFlow.waiting_price_input)
    await state.update_data(price_mid=mid, price_sid=sid)
    await callback.message.answer(
        f"✏️ Yangi narxni kiriting (faqat raqam, so'm):\nmaterial_id={mid}, size_id={sid}",
        reply_markup=admin_back_kb("cat_admin:prices"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_price_input)
async def cb_price_set(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(" ", "").replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ Faqat raqam kiriting.")
        return
    new_price = int(raw)
    data = await state.get_data()
    mid, sid = data.get("price_mid"), data.get("price_sid")
    async with async_session() as session:
        pm = await session.get(PriceMatrix, (mid, sid))
        if pm is None:
            pm = PriceMatrix(material_id=mid, size_id=sid, price=new_price)
            session.add(pm)
        else:
            pm.price = new_price
        await session.commit()
    await state.clear()
    price_str = f"{new_price:,}".replace(",", " ")
    await message.answer(
        f"✅ Narx yangilandi: {price_str} so'm",
        reply_markup=admin_back_kb("cat_admin:prices"),
    )


# ------------------- Generic name-input router -------------------

@router.message(AdminFlow.waiting_product_category)
async def admin_generic_name_input(message: Message, state: FSMContext):
    """Routes to category / material / size creation & editing."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Bo'sh bo'lmasin.")
        return
    data = await state.get_data()
    action = data.get("admin_action")
    async with async_session() as session:
        if action == "add_category":
            session.add(Category(name_uz=text))
            await session.commit()
            await message.answer("✅ Yangi kategoriya muvaffaqiyatli qo'shildi.", reply_markup=admin_back_kb("cat_admin:categories"))
        elif action == "edit_category":
            cid = data.get("edit_category_id")
            c = await session.get(Category, cid)
            if c:
                c.name_uz = text
                await session.commit()
                await message.answer(f"✅ Kategoriya nomi «{text}» deb o'zgartirildi.", reply_markup=admin_back_kb("cat_admin:categories"))
            else:
                await message.answer("Kategoriya topilmadi.", reply_markup=admin_back_kb("cat_admin:categories"))
        elif action == "add_material":
            session.add(Material(name_uz=text))
            await session.commit()
            await message.answer("✅ Yangi xomashyo qo'shildi.", reply_markup=admin_back_kb("cat_admin:materials"))
        elif action == "edit_material":
            mid = data.get("edit_material_id")
            m = await session.get(Material, mid)
            if m:
                m.name_uz = text
                await session.commit()
                await message.answer(f"✅ Xomashyo nomi «{text}» deb o'zgartirildi.", reply_markup=admin_back_kb("cat_admin:materials"))
            else:
                await message.answer("Xomashyo topilmadi.", reply_markup=admin_back_kb("cat_admin:materials"))
        elif action == "add_size":
            session.add(Size(name_uz=text))
            await session.commit()
            await message.answer("✅ Yangi razmer qo'shildi.", reply_markup=admin_back_kb("cat_admin:sizes"))
        elif action == "edit_size":
            sid = data.get("edit_size_id")
            sz = await session.get(Size, sid)
            if sz:
                sz.name_uz = text
                await session.commit()
                await message.answer(f"✅ Razmer «{text}» deb o'zgartirildi.", reply_markup=admin_back_kb("cat_admin:sizes"))
            else:
                await message.answer("Razmer topilmadi.", reply_markup=admin_back_kb("cat_admin:sizes"))
        else:
            await message.answer("Noma'lum amal. /admin bosing.")
    await state.clear()


# ------------------- Admin reply to user (FSM-bound) -------------------

@router.message(AdminFlow.waiting_admin_reply)
async def admin_reply_handler(message: Message, state: FSMContext):
    """If admin is in 'reply to user' state, send the text to the customer."""
    data = await state.get_data()
    order_id = data.get("reply_order_id")
    if not order_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Matn bo'sh bo'lishi mumkin emas.")
        return
    async with async_session() as session:
        from database.models import Order, User
        order = await session.get(Order, order_id)
        user = await session.get(User, order.user_id) if order else None
    if user is None:
        await message.answer("Mijoz topilmadi.")
        await state.clear()
        return
    from utils.security import get_bot
    bot = get_bot()
    if not bot:
        await message.answer("Bot hozircha ishga tushmagan.")
        await state.clear()
        return
    try:
        await bot.send_message(
            user.telegram_id,
            f"📨 Admin javobi (buyurtma #{order.order_number}):\n\n{text}",
        )
        await message.answer("✅ Xabar mijozga yuborildi.", reply_markup=admin_back_kb(f"admin:order:{order_id}"))
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    await state.clear()
