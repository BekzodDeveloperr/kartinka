"""Admin order management: list / filter / paginate / search by ID/number/name/phone/username."""
from __future__ import annotations

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy import func, or_, select

from database.db import async_session
from database.models import Order, User
from keyboards.admin_kb import (
    ORDER_STATUS_FLOW,
    STATUS_LABELS,
    admin_back_kb,
    admin_order_actions_kb,
    admin_orders_menu_kb,
)
from states.order_states import AdminFlow
from utils.security import IsAdminFilter
from utils.formatting import format_order_details

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

PER_PAGE = 5


async def _count_orders(session, status: str | None) -> int:
    q = select(func.count()).select_from(Order).where(Order.status != "draft")
    if status and status != "all":
        q = q.where(Order.status == status)
    return (await session.execute(q)).scalar_one()


async def _fetch_orders(session, status: str | None, page: int):
    q = (
        select(Order.id, Order.order_number, Order.status, Order.total_price, Order.created_at)
        .where(Order.status != "draft")
        .order_by(Order.created_at.desc())
        .limit(PER_PAGE)
        .offset(page * PER_PAGE)
    )
    if status and status != "all":
        q = q.where(Order.status == status)
    return (await session.execute(q)).all()


async def _get_perms(telegram_id: int) -> set[str]:
    from utils.security import get_admin_role_async, _role_permissions
    role = await get_admin_role_async(telegram_id)
    return _role_permissions().get(role, set()) if role else set()


@router.callback_query(F.data == "admin:orders")
async def cb_admin_orders_menu(callback: CallbackQuery):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await callback.message.edit_text(
        "📦 <b>Buyurtmalar bo'limi</b>\n\nFiltri tanlang:",
        reply_markup=admin_orders_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:orders:status:"))
async def cb_admin_orders_by_status(callback: CallbackQuery):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    parts = callback.data.split(":")
    status = parts[3] if len(parts) > 3 else "all"
    page = 0
    if len(parts) > 5 and parts[4] == "page":
        try:
            page = int(parts[5])
        except ValueError:
            page = 0
    async with async_session() as session:
        rows = await _fetch_orders(session, status, page)
        total = await _count_orders(session, status)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    if not rows:
        text = f"📭 Hech qanday buyurtma topilmadi ({STATUS_LABELS.get(status, status)})."
    else:
        lines = [f"📦 <b>{STATUS_LABELS.get(status, status)}</b> — {total} ta buyurtma:", ""]
        for oid, num, st, price, created in rows:
            lines.append(
                f"• #{num}  |  {STATUS_LABELS.get(st, st)}  |  "
                f"{format_price_local(price)} so'm  |  {created.strftime('%d.%m %H:%M')}"
            )
        lines.append("")
        lines.append("Batafsil uchun tugmalardan foydalaning:")
        text = "\n".join(lines)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for oid, num, st, price, created in rows:
        b.button(text=f"#{num} — {STATUS_LABELS.get(st, st)}", callback_data=f"admin:order:{oid}")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:orders:status:{status}:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:orders:status:{status}:page:{page + 1}"))
    if nav:
        b.row(*nav)
    b.button(text="⬅️ Buyurtmalar menyu", callback_data="admin:orders")
    b.adjust(1)
    await callback.message.edit_text(text, reply_markup=b.as_markup())
    await callback.answer()


def format_price_local(amount):
    if amount is None:
        amount = 0
    return f"{amount:,}".replace(",", " ")


@router.callback_query(F.data == "admin:orders:search")
async def cb_admin_orders_search(callback: CallbackQuery, state: FSMContext):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_order_search)
    await callback.message.edit_text(
        "🔍 Qidirish uchun yuboring:\n"
        "  • Buyurtma raqami (42 yoki 000042)\n"
        "  • Foydalanuvchi Telegram ID si\n"
        "  • Mijoz ismi (masalan, Aziz)\n"
        "  • Telefon raqam (oxirgi 9 raqam)\n"
        "  • Username (@username yoki username)",
        reply_markup=admin_back_kb("admin:orders"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_order_search)
async def admin_order_search_handler(message: Message, state: FSMContext):
    raw = (message.text or "").strip().lstrip("#").lstrip("@")
    await state.clear()
    async with async_session() as session:
        orders: list[Order] = []

        # 1) Try numeric (order number, order.id, telegram_id)
        if raw.isdigit():
            num_str = raw.zfill(6)
            res = await session.execute(
                select(Order).where(
                    or_(Order.order_number == num_str, Order.order_number == raw, Order.id == int(raw))
                )
            )
            orders = list(res.scalars().all())
            if not orders:
                user_q = await session.execute(
                    select(User).where(User.telegram_id == int(raw))
                )
                user = user_q.scalar_one_or_none()
                if user:
                    res2 = await session.execute(
                        select(Order).where(Order.user_id == user.id, Order.status != "draft")
                        .order_by(Order.created_at.desc())
                    )
                    orders = list(res2.scalars().all())

        # 2) Try phone (last 9 digits)
        if not orders:
            digits = "".join(c for c in raw if c.isdigit())
            if len(digits) >= 9:
                phone_tail = digits[-9:]
                res = await session.execute(
                    select(Order)
                    .join(User, Order.user_id == User.id)
                    .where(User.phone.like(f"%{phone_tail}%"), Order.status != "draft")
                )
                orders = list(res.scalars().all())

        # 3) Try username (case-insensitive)
        if not orders:
            uname = raw.lstrip("@").lower()
            res = await session.execute(
                select(Order)
                .join(User, Order.user_id == User.id)
                .where(func.lower(User.username) == uname, Order.status != "draft")
            )
            orders = list(res.scalars().all())

        # 4) Try full_name (substring, case-insensitive)
        if not orders:
            res = await session.execute(
                select(Order)
                .join(User, Order.user_id == User.id)
                .where(func.lower(User.full_name).like(f"%{raw.lower()}%"), Order.status != "draft")
                .order_by(Order.created_at.desc())
                .limit(20)
            )
            orders = list(res.scalars().all())

        if not orders:
            await message.answer(
                "Hech narsa topilmadi. /admin bosing.",
                reply_markup=admin_back_kb("admin:orders"),
            )
            return

        perms = await _get_perms(message.from_user.id)
        for order in orders:
            summary = await format_order_details(session, order)
            await message.answer(
                summary,
                reply_markup=admin_order_actions_kb(order.id, order.status, permissions=perms),
            )


async def edit_or_send_admin_message(callback: CallbackQuery, text: str, reply_markup=None):
    if callback.message and callback.message.photo:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(
    F.data.startswith("admin:order:")
    & ~F.data.contains(":set:")
    & ~F.data.contains(":reply")
    & ~F.data.contains(":reqpay")
    & ~F.data.contains(":photo")
)
async def cb_admin_open_order(callback: CallbackQuery):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, oid_str = callback.data.split(":")
        order_id = int(oid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order is None:
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        summary = await format_order_details(session, order)
    await edit_or_send_admin_message(
        callback,
        summary,
        reply_markup=admin_order_actions_kb(order.id, order.status, permissions=perms),
    )
    await callback.answer()


@router.callback_query(F.data.contains(":photo"))
async def cb_admin_view_order_photo(callback: CallbackQuery, bot: Bot):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer()
        return
    try:
        order_id = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    async with async_session() as session:
        items = (
            await session.execute(
                select(OrderItem, Product)
                .join(Product, OrderItem.product_id == Product.id)
                .where(OrderItem.order_id == order_id)
            )
        ).all()
        if not items:
            await callback.answer("Rasm topilmadi.", show_alert=True)
            return
        for item, product in items:
            if product and product.photo_file_id:
                caption = f"🖼 Buyurtma #{order_id} - Kartinka #{product.id}\n{product.caption_uz or ''}"
                try:
                    await bot.send_photo(callback.from_user.id, photo=product.photo_file_id, caption=caption)
                except Exception as e:
                    await callback.answer(f"Rasm yuborishda xatolik: {e}", show_alert=True)
                    return
        await callback.answer("Rasm yuborildi 🖼")


@router.callback_query(F.data.contains(":set:"))
async def cb_admin_set_status(callback: CallbackQuery, bot: Bot):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) < 5 or parts[3] != "set":
        await callback.answer()
        return
    try:
        order_id = int(parts[2])
        new_status = parts[4]
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order is None:
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        order.status = new_status
        await session.commit()
        summary = await format_order_details(session, order)
        # Notify customer
        from services.notifications import notify_user_status_change
        await notify_user_status_change(bot, order, new_status)
    await edit_or_send_admin_message(
        callback,
        summary + f"\n\n✅ Status o'zgartirildi: {STATUS_LABELS.get(new_status, new_status)}",
        reply_markup=admin_order_actions_kb(order.id, new_status, permissions=perms),
    )
    await callback.answer("Status yangilandi")


@router.callback_query(F.data.endswith(":reqpay"))
async def cb_admin_reqpay(callback: CallbackQuery, bot: Bot):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer()
        return
    try:
        order_id = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    async with async_session() as session:
        order = await session.get(Order, order_id)
        user = await session.get(User, order.user_id) if order else None
        if order is None or user is None:
            await callback.answer("Topilmadi.", show_alert=True)
            return
    from keyboards.user_kb import pay_request_kb
    from utils.security import get_admin_username_async
    from utils.i18n import get_user_language
    lang = await get_user_language(user.telegram_id)
    admin_username = await get_admin_username_async()
    try:
        await bot.send_message(
            user.telegram_id,
            f"💳 Buyurtma #{order.order_number} uchun to'lovni amalga oshirish vaqti keldi.\n\n"
            "Quyidagi tugmalar orqali admin bilan bog'lanishingiz mumkin:",
            reply_markup=pay_request_kb(order.id, order.order_number, admin_username, user.telegram_id, lang),
        )
        await callback.answer("Mijozga to'lov so'rovi yuborildi ✅", show_alert=True)
    except Exception as e:
        await callback.answer(f"Xatolik: {e}", show_alert=True)


@router.callback_query(F.data.endswith(":reply"))
async def cb_admin_reply_to_user(callback: CallbackQuery, state: FSMContext):
    perms = await _get_perms(callback.from_user.id)
    if "orders" not in perms:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer()
        return
    try:
        order_id = int(parts[2])
    except ValueError:
        await callback.answer()
        return
    await state.set_state(AdminFlow.waiting_admin_reply)
    await state.update_data(reply_order_id=order_id)
    await callback.message.answer(
        "✏️ Mijozga yubormoqchi bo'lgan matningizni kiriting:",
        reply_markup=admin_back_kb(f"admin:order:{order_id}"),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_admin_reply)
async def admin_reply_to_user_handler(message: Message, state: FSMContext, bot: Bot):
    perms = await _get_perms(message.from_user.id)
    if "orders" not in perms:
        await state.clear()
        return
    data = await state.get_data()
    order_id = data.get("reply_order_id")
    await state.clear()
    if not order_id:
        await message.answer("Buyurtma ID si topilmadi.")
        return
    async with async_session() as session:
        order = await session.get(Order, order_id)
        user = await session.get(User, order.user_id) if order else None
        if not order or not user:
            await message.answer("Mijoz topilmadi.")
            return
        text = (message.text or "").strip()
        if not text:
            await message.answer("Matn bo'sh bo'lishi mumkin emas.")
            return
        try:
            msg_to_user = (
                f"📩 <b>ADMIN JAVOBI:</b>\n\n"
                f"🧾 <b>Buyurtma #{order.order_number}</b>\n\n"
                f"{text}"
            )
            await bot.send_message(user.telegram_id, msg_to_user)
            await message.answer(
                f"✅ Xabar mijozga ({user.full_name or user.telegram_id}) muvaffaqiyatli yetkazildi!",
                reply_markup=admin_back_kb(f"admin:order:{order_id}"),
            )
        except Exception as e:
            await message.answer(f"❌ Xabarni yuborishda xatolik: {e}")
