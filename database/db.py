"""Async engine, session factory, schema init and seed data."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import ADMIN_IDS, DATABASE_URL
from database.models import (
    AdminUser,
    Base,
    BotSetting,
    Category,
    Material,
    PriceMatrix,
    Size,
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables if missing, then seed minimal demo data on first run."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_initial_data()


async def _seed_initial_data() -> None:
    # Categories (multilingual)
    if (await _count(Category)) == 0:
        new_cats = [
            Category(name_uz="Mehmonxona uchun", name_ru="Для гостиницы", name_en="For hotel"),
            Category(name_uz="Salon uchun", name_ru="Для салона", name_en="For salon"),
        ]
        async with async_session() as s:
            s.add_all(new_cats)
            await s.commit()

    # Materials (multilingual)
    if (await _count(Material)) == 0:
        async with async_session() as s:
            s.add_all([
                Material(
                    name_uz="Oddiy holst",
                    name_ru="Обычный холст",
                    name_en="Standard canvas",
                ),
                Material(
                    name_uz="Premium holst",
                    name_ru="Премиум холст",
                    name_en="Premium canvas",
                ),
                Material(
                    name_uz="Yog'och ramkali",
                    name_ru="Деревянная рамка",
                    name_en="Wooden frame",
                ),
            ])
            await s.commit()

    # Sizes (multilingual)
    if (await _count(Size)) == 0:
        async with async_session() as s:
            s.add_all([
                Size(name_uz="30x40", name_ru="30x40", name_en="30x40"),
                Size(name_uz="40x60", name_ru="40x60", name_en="40x60"),
                Size(name_uz="60x90", name_ru="60x90", name_en="60x90"),
                Size(name_uz="80x120", name_ru="80x120", name_en="80x120"),
            ])
            await s.commit()

    # Price matrix
    if (await _count(PriceMatrix)) == 0:
        async with async_session() as s:
            mats = (await s.execute(select(Material).order_by(Material.id))).scalars().all()
            sizes = (await s.execute(select(Size).order_by(Size.id))).scalars().all()
            base_prices = {0: 50_000, 1: 80_000, 2: 120_000}
            size_mult = {0: 1.0, 1: 1.5, 2: 2.0, 3: 3.0}
            for mi, m in enumerate(mats):
                for si, sz in enumerate(sizes):
                    price = int(base_prices.get(mi, 50_000) * size_mult.get(si, 1.0))
                    s.add(PriceMatrix(material_id=m.id, size_id=sz.id, price=price))
            await s.commit()

    # Admin users from .env ADMIN_IDS — all start as super_admin
    if (await _count(AdminUser)) == 0:
        async with async_session() as s:
            for aid in ADMIN_IDS:
                s.add(AdminUser(telegram_id=aid, role="super_admin"))
            await s.commit()

    # Default settings
    defaults = {
        "notify_new_user": "1",
        "notify_dropoff": "0",
        "notify_payment_request_cooldown_min": "5",
        "broadcast_batch_size": "10",
    }
    async with async_session() as s:
        for k, v in defaults.items():
            existing = await s.get(BotSetting, k)
            if existing is None:
                s.add(BotSetting(key=k, value=v))
        await s.commit()


async def _count(model) -> int:
    async with async_session() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()
