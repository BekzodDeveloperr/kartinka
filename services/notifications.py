"""Outbound notifications: real-time admin alerts + customer status updates."""
from __future__ import annotations

from aiogram import Bot

from config import ADMIN_IDS, ADMIN_USERNAME
from database.db import async_session
from database.models import Order, User, BotSetting
from utils.formatting import format_order_details, format_price
from utils.i18n import t, get_user_language


async def notify_admin_new_order(bot: Bot, summary: str, customer_telegram_id: int, order_id: int):
    """Send a 'new order arrived' alert to all admins with action buttons."""
    from keyboards.admin_kb import admin_order_actions_kb
    from utils.security import get_admin_role_async, role_has_permission
    from database.models import OrderItem, Product, AdminUser
    from sqlalchemy import select

    text = (
        f"🔔 <b>YANGI BUYURTMA!</b>\n\n"
        f"{summary}\n\n"
        f"Mijoz Telegram ID: <code>{customer_telegram_id}</code>"
    )

    async with async_session() as s:
        extra = (await s.execute(select(AdminUser.telegram_id))).scalars().all()
        item = (
            await s.execute(
                select(OrderItem, Product)
                .join(Product, OrderItem.product_id == Product.id)
                .where(OrderItem.order_id == order_id)
                .limit(1)
            )
        ).first()
        photo_id = item[1].photo_file_id if (item and item[1]) else None

    admin_tg_ids = set(ADMIN_IDS)
    admin_tg_ids.update(extra)

    for admin_id in admin_tg_ids:
        role = await get_admin_role_async(admin_id)
        if not role_has_permission(role, "orders"):
            continue
        try:
            if photo_id:
                await bot.send_photo(
                    admin_id,
                    photo=photo_id,
                    caption=text,
                    reply_markup=admin_order_actions_kb(order_id, "yangi", permissions={"orders"}),
                )
            else:
                await bot.send_message(
                    admin_id,
                    text,
                    reply_markup=admin_order_actions_kb(order_id, "yangi", permissions={"orders"}),
                )
        except Exception:
            pass


async def notify_admin_payment_request(bot: Bot, order: Order, user: User):
    """When user clicks 'Admin bilan bog'lanish (to'lov uchun)'."""
    from keyboards.admin_kb import admin_order_actions_kb
    from utils.security import get_admin_role_async, role_has_permission
    from database.models import AdminUser
    from sqlalchemy import select

    username_line = f"Username: @{user.username}" if user.username else "Username: (yo'q)"
    text = (
        f"💳 <b>TO'LOV SO'ROVI</b>\n\n"
        f"Foydalanuvchi: {user.full_name or '-'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"{username_line}\n"
        f"Buyurtma raqami: #{order.order_number}\n"
        f"Umumiy summa: {format_price(order.total_price)} so'm\n\n"
        f"Avto-xabar: \"Assalomu alaykum, meni ID: {user.telegram_id}, "
        f"#{order.order_number} raqamli buyurtmam uchun to'lov amalga oshirmoqchiman.\"\n\n"
        f"Admin panel: /admin → Buyurtmalar → #{order.order_number}"
    )

    admin_tg_ids = set(ADMIN_IDS)
    async with async_session() as s:
        extra = (await s.execute(select(AdminUser.telegram_id))).scalars().all()
    admin_tg_ids.update(extra)

    for admin_id in admin_tg_ids:
        role = await get_admin_role_async(admin_id)
        if not role_has_permission(role, "orders"):
            continue
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=admin_order_actions_kb(order.id, order.status, permissions={"orders"}),
            )
        except Exception:
            pass


async def notify_user_status_change(bot: Bot, order: Order, new_status: str):
    """Customer gets a heads-up when admin moves their order to a new status."""
    if not order.user_id:
        return
    async with async_session() as session:
        user = await session.get(User, order.user_id)
        if not user:
            return
    lang = await get_user_language(user.telegram_id)
    label_map = {
        "jarayonda": t(lang, "status_progress") + " 🔧",
        "tayyor": t(lang, "status_ready") + " ✅",
        "yetkazildi": t(lang, "status_delivered") + " 📦",
        "bekor_qilindi": t(lang, "status_cancelled") + " ❌",
    }
    label = label_map.get(new_status, new_status)
    from utils.security import get_admin_username_async
    admin_uname = await get_admin_username_async()
    try:
        await bot.send_message(
            user.telegram_id,
            t(lang, "status_changed", num=order.order_number, label=label, admin=admin_uname),
        )
    except Exception:
        pass

    # If delivered, send review request
    if new_status == "yetkazildi":
        from keyboards.user_kb import review_kb
        try:
            await bot.send_message(
                user.telegram_id,
                t(lang, "review_ask", num=order.order_number),
                reply_markup=review_kb(order.id, lang),
            )
        except Exception:
            pass


async def notify_admin_user_registered(bot: Bot, user: User):
    """Notify admins about a fresh registration."""
    username_line = f"Username: @{user.username}" if user.username else "Username: (yo'q)"
    text = (
        f"👤 <b>YANGI MIJOZ RO'YXATDAN O'TDI!</b>\n\n"
        f"<b>Ism:</b> {user.full_name or '-'}\n"
        f"<b>Tel:</b> {user.phone or '-'}\n"
        f"<b>Manzil:</b> {user.address or '-'}\n"
        f"<b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
        f"{username_line}"
    )
    from database.models import AdminUser
    from sqlalchemy import select
    admin_tg_ids = set(ADMIN_IDS)
    async with async_session() as s:
        extra = (await s.execute(select(AdminUser.telegram_id))).scalars().all()
    admin_tg_ids.update(extra)
    for admin_id in admin_tg_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
