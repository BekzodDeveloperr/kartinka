"""Text formatting helpers (prices, order details, markdown escape)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, OrderItem, Product, Material, Size, User, Review
from utils.i18n import t, get_entity_name


def format_price(amount: int | None) -> str:
    if amount is None:
        amount = 0
    return f"{amount:,}".replace(",", " ")


def escape_md(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _status_key(status: str) -> str:
    """Map DB status to i18n key."""
    return {
        "draft": "status_draft",
        "yangi": "status_new",
        "avans_kutilmoqda": "status_avans",
        "jarayonda": "status_progress",
        "tayyor": "status_ready",
        "yetkazildi": "status_delivered",
        "bekor_qilindi": "status_cancelled",
        "tark_etdi": "status_left",
    }.get(status, "status_new")


def _deadline_key(deadline: str) -> str:
    return {
        "tez": "deadline_fast",
        "standard": "deadline_standard",
    }.get(deadline, deadline)


async def format_order_details(session: AsyncSession, order: Order, lang: str = "uz") -> str:
    """Render a human-readable order summary in the given language."""
    user: User | None = await session.get(User, order.user_id)
    items_q = await session.execute(
        select(OrderItem, Product, Material, Size)
        .join(Product, OrderItem.product_id == Product.id, isouter=True)
        .join(Material, OrderItem.material_id == Material.id, isouter=True)
        .join(Size, OrderItem.size_id == Size.id, isouter=True)
        .where(OrderItem.order_id == order.id)
    )

    lines: list[str] = []
    lines.append(f"🧾 {t(lang, 'status_draft').split(' ')[0] if False else 'Buyurtma'}: <b>#{order.order_number}</b>")
    status_label = t(lang, _status_key(order.status))
    lines.append(f"📊 {t(lang, 'admin_stats').split(' ')[0] if False else 'Status'}: {status_label}")
    if user:
        lines.append("")
        lines.append("👤 Mijoz:" if lang == "uz" else ("👤 Клиент:" if lang == "ru" else "👤 Customer:"))
        lines.append(f"   • {'Ism' if lang=='uz' else ('Имя' if lang=='ru' else 'Name')}: {user.full_name or '-'}")
        lines.append(f"   • {'Tel' if lang=='uz' else ('Тел' if lang=='ru' else 'Tel')}: {user.phone or '-'}")
        lines.append(f"   • {'Manzil' if lang=='uz' else ('Адрес' if lang=='ru' else 'Address')}: {user.address or '-'}")
        if user.username:
            lines.append(f"   • Username: @{user.username}")
        lines.append(f"   • Telegram ID: <code>{user.telegram_id}</code>")
    lines.append("")
    items_label = "📦 Mahsulotlar" if lang == "uz" else ("📦 Товары" if lang == "ru" else "📦 Items")
    lines.append(items_label + ":")
    from database.models import Category
    for idx, (item, product, material, size) in enumerate(items_q.all(), start=1):
        cat_name = "-"
        if product and product.category_id:
            cat = await session.get(Category, product.category_id)
            if cat:
                cat_name = await get_entity_name(cat, lang)
        pcaption = await get_entity_name(product, lang) if product else "-"
        pname = f"🖼 <b>Kartinka #{item.product_id}</b> ({cat_name})"
        mname = await get_entity_name(material, lang) if material else "-"
        sname = (await get_entity_name(size, lang)) if size else (f"{item.custom_size} (Maxsus)" if getattr(item, "custom_size", None) else "-")
        lines.append(f"   {idx}. {pname}")
        if pcaption and pcaption != "-":
            lines.append(f"      • {'Tavsif' if lang=='uz' else ('Описание' if lang=='ru' else 'Caption')}: {pcaption}")
        lines.append(f"      • {'Matosi' if lang=='uz' else ('Материал' if lang=='ru' else 'Material')}: {mname}  •  {'O\'lchami' if lang=='uz' else ('Размер' if lang=='ru' else 'Size')}: {sname}")
        lines.append(f"      • {'Narxi' if lang=='uz' else ('Цена' if lang=='ru' else 'Price')}: {format_price(item.price)} so'm")
    lines.append("")
    if order.discount and order.discount > 0:
        lines.append(f"🎟 {'Chegirma' if lang=='uz' else ('Скидка' if lang=='ru' else 'Discount')}: -{format_price(order.discount)} so'm")
        final = (order.total_price or 0) - order.discount
        lines.append(f"💰 {'Jami summa' if lang=='uz' else ('Итого' if lang=='ru' else 'Total')}: <b>{format_price(final)} so'm</b>")
    else:
        lines.append(f"💰 {'Jami summa' if lang=='uz' else ('Итого' if lang=='ru' else 'Total')}: <b>{format_price(order.total_price)} so'm</b>")
    if order.deadline_type:
        dl_label = t(lang, _deadline_key(order.deadline_type))
        lines.append(f"⏱ {'Muddat' if lang=='uz' else ('Срок' if lang=='ru' else 'Deadline')}: {dl_label}")
    if order.promo_code:
        lines.append(f"🎟 Promo: <code>{order.promo_code}</code>")

    # Admin-only: show review if exists
    if order.status == "yetkazildi" or order.status == "tayyor":
        review = (
            await session.execute(
                select(Review).where(Review.order_id == order.id)
            )
        ).scalar_one_or_none()
        if review:
            stars = "⭐" * review.rating
            lines.append("")
            lines.append(f"⭐ {'Baholash' if lang=='uz' else ('Оценка' if lang=='ru' else 'Review')}: {stars} ({review.rating}/5)")
            if review.comment:
                lines.append(f"💬 {review.comment}")

    return "\n".join(lines)
