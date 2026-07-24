"""Report generators used by APScheduler (daily / weekly) and admin panel."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, OrderItem, Product, User, UserTagHistory
from utils.formatting import format_price


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


async def general_stats(session: AsyncSession) -> str:
    total_users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    total_orders = (
        await session.execute(
            select(func.count()).select_from(Order).where(Order.status != "draft")
        )
    ).scalar_one()
    total_revenue = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_price - func.coalesce(Order.discount, 0)), 0))
            .where(Order.status != "draft", Order.status != "bekor_qilindi")
        )
    ).scalar_one()
    by_status = (
        await session.execute(
            select(Order.status, func.count()).where(Order.status != "draft").group_by(Order.status)
        )
    ).all()
    avg_rating = (
        await session.execute(
            select(func.avg(
                __import__("database.models", fromlist=["Review"]).Review.rating
            ))
        )
    ).scalar_one()
    lines = [
        "📊 <b>Umumiy statistika</b>",
        "",
        f"👥 Foydalanuvchilar: {total_users}",
        f"🧾 Buyurtmalar: {total_orders}",
        f"💰 Umumiy aylanma (chegirma bilan): {format_price(total_revenue)} so'm",
    ]
    if avg_rating:
        lines.append(f"⭐ O'rtacha baho: {avg_rating:.2f} / 5")
    lines.append("")
    lines.append("Status bo'yicha:")
    for st, cnt in by_status:
        lines.append(f"   • {st}: {cnt}")
    return "\n".join(lines)


async def dropoff_stats(session: AsyncSession) -> str:
    rows = (
        await session.execute(
            select(User.tag, func.count()).group_by(User.tag).order_by(func.count().desc())
        )
    ).all()
    lines = ["📉 <b>Drop-off statistikasi (joriy tag)</b>", ""]
    if not rows:
        lines.append("(ma'lumot yo'q)")
        return "\n".join(lines)
    for tag, cnt in rows:
        lines.append(f"   • {tag}: {cnt}")
    return "\n".join(lines)


async def funnel_stats(session: AsyncSession) -> str:
    """Build a conversion funnel from tag history.

    For each tag, count distinct users who have EVER reached that tag.
    """
    # Ordered stages
    stages = [
        ("start_bosdi", "1. /start bosgan"),
        ("kontakt_berdi", "2. Kontakt bergan"),
        ("turni_tanladi", "3. Turni tanlagan"),
        ("mahsulot_tanladi", "4. Mahsulot tanlagan"),
        ("narxni_kordi", "5. Narxni ko'rgan"),
        ("buyurtma_berdi", "6. Buyurtma bergan"),
        ("yetkazildi", "7. Yetkazilgan"),
    ]
    lines = ["🪣 <b>Konversiya funnelsi</b>", ""]
    for tag, label in stages:
        # Count distinct users who ever had this tag in history OR have it now
        from_history = (
            await session.execute(
                select(func.count(func.distinct(UserTagHistory.user_id)))
                .where(UserTagHistory.new_tag == tag)
            )
        ).scalar_one()
        current = (
            await session.execute(
                select(func.count()).select_from(User).where(User.tag == tag)
            )
        ).scalar_one()
        total = max(from_history, current)
        lines.append(f"{label}: <b>{total}</b>")
    return "\n".join(lines)


async def top_products(session: AsyncSession) -> str:
    res = await session.execute(
        select(Product.caption_uz, Product.id, func.count(OrderItem.id))
        .join(OrderItem, OrderItem.product_id == Product.id, isouter=True)
        .group_by(Product.id)
        .order_by(func.count(OrderItem.id).desc())
        .limit(10)
    )
    rows = res.all()
    lines = ["🏆 <b>Eng ko'p tanlangan mahsulotlar</b>", ""]
    if not rows:
        lines.append("(ma'lumot yo'q)")
        return "\n".join(lines)
    for i, (caption, pid, cnt) in enumerate(rows, start=1):
        lines.append(f"{i}. {caption or f'#{pid}'} — {cnt} ta")
    return "\n".join(lines)


async def build_daily_report(session: AsyncSession, target_date: datetime) -> str:
    """Compose the daily report message for the given date."""
    start = _start_of_day(target_date)
    end = start + timedelta(days=1)

    new_users = (
        await session.execute(
            select(func.count()).select_from(User).where(User.first_seen_at >= start, User.first_seen_at < end)
        )
    ).scalar_one()
    finished_orders = (
        await session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.status != "draft", Order.created_at >= start, Order.created_at < end)
        )
    ).scalar_one()
    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_price - func.coalesce(Order.discount, 0)), 0))
            .where(Order.status != "draft", Order.status != "bekor_qilindi",
                   Order.created_at >= start, Order.created_at < end)
        )
    ).scalar_one()

    dropoff = (
        await session.execute(
            select(User.tag, func.count())
            .where(User.last_active_at >= start, User.last_active_at < end)
            .group_by(User.tag)
        )
    ).all()

    top_today = (
        await session.execute(
            select(Product.caption_uz, func.count())
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.created_at >= start, Order.created_at < end)
            .group_by(Product.id)
            .order_by(func.count().desc())
            .limit(3)
        )
    ).all()

    lines = [
        f"📅 <b>Kunlik hisobot — {start.strftime('%d.%m.%Y')}</b>",
        "",
        f"👥 Yangi foydalanuvchilar: {new_users}",
        f"🧾 Yakunlangan buyurtmalar: {finished_orders}",
        f"💰 Umumiy aylanma: {format_price(revenue)} so'm",
        "",
        "📉 Bugungi drop-off:",
    ]
    if dropoff:
        for tag, cnt in dropoff:
            lines.append(f"   • {tag}: {cnt}")
    else:
        lines.append("   (hech narsa)")
    lines.append("")
    lines.append("🏆 Bugun eng ko'p tanlangan mahsulotlar:")
    if top_today:
        for cap, cnt in top_today:
            lines.append(f"   • {cap}: {cnt}")
    else:
        lines.append("   (hech narsa)")
    return "\n".join(lines)


async def build_weekly_report(session: AsyncSession) -> str:
    end = _utcnow()
    start = end - timedelta(days=7)

    starts = (
        await session.execute(
            select(func.count()).select_from(User).where(User.first_seen_at >= start)
        )
    ).scalar_one()
    finished = (
        await session.execute(
            select(func.count()).select_from(Order)
            .where(Order.status != "draft", Order.created_at >= start)
        )
    ).scalar_one()
    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_price - func.coalesce(Order.discount, 0)), 0))
            .where(Order.status != "draft", Order.status != "bekor_qilindi",
                   Order.created_at >= start)
        )
    ).scalar_one()
    by_status = (
        await session.execute(
            select(Order.status, func.count())
            .where(Order.status != "draft", Order.created_at >= start)
            .group_by(Order.status)
        )
    ).all()

    conversion = (finished / starts * 100) if starts else 0
    lines = [
        f"📅 <b>Haftalik hisobot — oxirgi 7 kun</b>",
        "",
        f"👥 /start bosganlar: {starts}",
        f"🧾 Yakunlangan buyurtmalar: {finished}",
        f"📈 Conversion: {conversion:.1f}%",
        f"💰 Aylanma: {format_price(revenue)} so'm",
        "",
        "Status bo'yicha taqsimot:",
    ]
    for st, cnt in by_status:
        lines.append(f"   • {st}: {cnt}")
    return "\n".join(lines)
