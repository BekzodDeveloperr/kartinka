"""Reviews viewer (admin-only). Customers can't see other users' reviews."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from database.db import async_session
from database.models import Order, Review, User
from keyboards.admin_kb import admin_back_kb, admin_reviews_kb
from utils.security import IsAdminFilter, get_admin_role_async, role_has_permission

router = Router()
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "admin:reviews")
async def cb_admin_reviews(callback: CallbackQuery):
    role = await get_admin_role_async(callback.from_user.id)
    if not role_has_permission(role, "stats") and not role_has_permission(role, "orders"):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    async with async_session() as session:
        reviews = (
            await session.execute(
                select(Review.id, Order.order_number, Review.rating, Review.comment, User.telegram_id)
                .join(Order, Review.order_id == Order.id)
                .join(User, Review.user_id == User.id)
                .order_by(Review.created_at.desc())
                .limit(50)
            )
        ).all()
    avg_rating = (
        await session.execute(select(func.avg(Review.rating)))
    ).scalar_one() if reviews else None

    text_parts = ["⭐ <b>Sharhlar</b>", ""]
    if avg_rating:
        text_parts.append(f"📊 O'rtacha baho: <b>{avg_rating:.2f} / 5</b>")
        text_parts.append(f"📝 Jami sharhlar: {len(reviews)}")
        text_parts.append("")
    if not reviews:
        text_parts.append("Hozircha sharhlar yo'q.")
        await callback.message.edit_text("\n".join(text_parts), reply_markup=admin_back_kb("admin:panel"))
        await callback.answer()
        return

    await callback.message.edit_text(
        "\n".join(text_parts),
        reply_markup=admin_reviews_kb(reviews),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("review:open:"))
async def cb_review_open(callback: CallbackQuery):
    role = await get_admin_role_async(callback.from_user.id)
    if not role_has_permission(role, "stats") and not role_has_permission(role, "orders"):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    try:
        _, _, rid_str = callback.data.split(":")
        rid = int(rid_str)
    except (ValueError, IndexError):
        await callback.answer()
        return
    async with async_session() as session:
        review = await session.get(Review, rid)
        if review is None:
            await callback.answer("Topilmadi.", show_alert=True)
            return
        order = await session.get(Order, review.order_id)
        user = await session.get(User, review.user_id)
        stars = "⭐" * review.rating
        text = (
            f"⭐ <b>Sharh #{review.id}</b>\n\n"
            f"📦 Buyurtma: #{order.order_number if order else '?'}\n"
            f"👤 Mijoz: {user.full_name if user else '?'} (ID: <code>{user.telegram_id if user else '?'}</code>)\n"
            f"⭐ Baho: {stars} ({review.rating}/5)\n"
            f"💬 Izoh: {review.comment or '(izohsiz)'}\n"
            f"📅 Sana: {review.created_at.strftime('%d.%m.%Y %H:%M') if review.created_at else '-'}"
        )
    await callback.message.edit_text(text, reply_markup=admin_back_kb("admin:reviews"))
    await callback.answer()
