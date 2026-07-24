"""SQLAlchemy 2.0 declarative ORM models for the canvas-order bot.

DB-agnostic (SQLite <-> PostgreSQL via DATABASE_URL).
All timestamps are timezone-aware UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(Text)
    full_name = Column(Text)
    phone = Column(Text)
    address = Column(Text)
    tag = Column(Text, default="start_bosdi", index=True)
    current_state = Column(Text)
    reminder_sent = Column(Integer, default=0)
    language = Column(Text, default="uz")  # uz / ru / en
    first_seen_at = Column(DateTime(timezone=True), default=_utcnow)
    last_active_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_uz = Column(Text, nullable=False)
    name_ru = Column(Text)
    name_en = Column(Text)

    products = relationship(
        "Product", back_populates="category", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)
    photo_file_id = Column(Text, nullable=False)
    caption_uz = Column(Text)
    caption_ru = Column(Text)
    caption_en = Column(Text)
    order_index = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    category = relationship("Category", back_populates="products")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_uz = Column(Text, nullable=False)
    name_ru = Column(Text)
    name_en = Column(Text)


class Size(Base):
    __tablename__ = "sizes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_uz = Column(Text, nullable=False)
    name_ru = Column(Text)
    name_en = Column(Text)


class PriceMatrix(Base):
    __tablename__ = "price_matrix"

    material_id = Column(
        Integer, ForeignKey("materials.id"), primary_key=True
    )
    size_id = Column(Integer, ForeignKey("sizes.id"), primary_key=True)
    price = Column(Integer, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(Text, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    status = Column(Text, default="draft", index=True)
    deadline_type = Column(Text)
    total_price = Column(Integer, default=0)
    discount = Column(Integer, default=0)  # applied promo discount in so'm
    promo_code = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="orders")
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    review = relationship("Review", back_populates="order", uselist=False, cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    size_id = Column(Integer, ForeignKey("sizes.id"), nullable=True)
    custom_size = Column(Text, nullable=True)
    price = Column(Integer)

    order = relationship("Order", back_populates="items")


class BroadcastLog(Base):
    __tablename__ = "broadcasts_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger)
    target_tag = Column(Text)
    message = Column(Text)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    blocked_user_ids = Column(Text)  # comma-separated blocked user telegram IDs
    sent_at = Column(DateTime(timezone=True), default=_utcnow)


class AdminUser(Base):
    """Admin roles: super_admin | operator | moliyachi."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(Text)
    role = Column(Text, default="operator")  # super_admin | operator | moliyachi
    added_at = Column(DateTime(timezone=True), default=_utcnow)
    added_by = Column(BigInteger, nullable=True)


class Review(Base):
    """Customer review of a delivered order. Visible to admins only."""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1..5
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    order = relationship("Order", back_populates="review")
    user = relationship("User", back_populates="reviews")


class PromoCode(Base):
    """Promo / discount code."""
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, unique=True, nullable=False, index=True)
    discount_type = Column(Text, default="percent")  # percent | fixed
    discount_value = Column(Integer, nullable=False)  # percent: 0..100, fixed: so'm
    min_order_amount = Column(Integer, default=0)  # apply only if total >= this
    max_uses = Column(Integer, default=0)  # 0 = unlimited
    uses_count = Column(Integer, default=0)
    valid_from = Column(DateTime(timezone=True), default=_utcnow)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class PromoUsage(Base):
    """Track which user used which promo on which order (prevent reuse + history)."""
    __tablename__ = "promo_usages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    promo_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    used_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("user_id", "promo_id", name="uq_user_promo"),)


class UserTagHistory(Base):
    """Track every tag transition for analytics (drop-off funnel accuracy)."""
    __tablename__ = "user_tag_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    old_tag = Column(Text)
    new_tag = Column(Text, nullable=False)
    changed_at = Column(DateTime(timezone=True), default=_utcnow)


class BotSetting(Base):
    """Key-value store for runtime toggles (notify_new_user, notify_dropoff, etc.)."""
    __tablename__ = "bot_settings"

    key = Column(Text, primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)


class PaymentRequestLog(Base):
    """Track 'admin bilan bog'lanish' clicks to prevent spam."""
    __tablename__ = "payment_request_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_at = Column(DateTime(timezone=True), default=_utcnow)
