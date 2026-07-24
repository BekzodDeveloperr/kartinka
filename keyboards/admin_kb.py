"""All admin-facing inline keyboards. Only rendered for admin users.

Role-based access:
  super_admin : full (panel + broadcast + settings + admins + catalog + promo + reviews)
  operator    : orders + catalog + stats + promo + reviews
  moliyachi   : orders + stats + export + promo
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Admin status flow
ORDER_STATUS_FLOW = [
    "yangi",
    "jarayonda",
    "tayyor",
    "yetkazildi",
]

STATUS_LABELS = {
    "draft": "Qoralama",
    "yangi": "Yangi",
    "jarayonda": "Jarayonda",
    "tayyor": "Tayyor",
    "yetkazildi": "Yetkazildi",
    "bekor_qilindi": "Bekor qilindi",
    "tark_etdi": "Tark etdi",
}


def admin_panel_kb(permissions: set[str] | None = None):
    """Build panel keyboard based on permissions."""
    perms = permissions or set()
    b = InlineKeyboardBuilder()
    if "orders" in perms:
        b.button(text="📦 Buyurtmalar", callback_data="admin:orders")
    if "users" in perms or "orders" in perms:
        b.button(text="👥 Foydalanuvchilar", callback_data="admin:users")
    if "broadcast" in perms:
        b.button(text="📢 Xabar yuborish (broadcast)", callback_data="admin:broadcast")
    if "catalog" in perms:
        b.button(text="🛠 Katalog boshqaruvi", callback_data="admin:catalog")
    if "promo" in perms:
        b.button(text="🎟 Promokodlar", callback_data="admin:promo")
    if "stats" in perms:
        b.button(text="📊 Statistika", callback_data="admin:stats")
    if "export" in perms:
        b.button(text="📋 Excel eksport", callback_data="admin:export")
    b.button(text="⭐ Sharhlar", callback_data="admin:reviews")
    if "settings" in perms:
        b.button(text="⚙️ Sozlamalar", callback_data="admin:settings")
    if "admins" in perms:
        b.button(text="👮 Adminlar", callback_data="admin:admins")
    b.button(text="🚪 Yopish", callback_data="admin:close")
    b.adjust(1)
    return b.as_markup()


def admin_orders_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🆕 Yangi", callback_data="admin:orders:status:yangi")
    b.button(text="💳 Avans kutilmoqda", callback_data="admin:orders:status:avans_kutilmoqda")
    b.button(text="🔧 Jarayonda", callback_data="admin:orders:status:jarayonda")
    b.button(text="✅ Tayyor", callback_data="admin:orders:status:tayyor")
    b.button(text="📦 Yetkazildi", callback_data="admin:orders:status:yetkazildi")
    b.button(text="❌ Bekor", callback_data="admin:orders:status:bekor_qilindi")
    b.button(text="📋 Barchasi", callback_data="admin:orders:status:all")
    b.button(text="🔍 Qidirish (ID/raqam/ism/tel)", callback_data="admin:orders:search")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(2, 2, 2, 1, 1, 1)
    return b.as_markup()


def admin_pagination_kb(prefix: str, page: int, total_pages: int, extra_back: str = "admin:orders"):
    b = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{max(1, total_pages)}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}:page:{page + 1}"))
    if nav:
        b.row(*nav)
    b.button(text="⬅️ Orqaga", callback_data=extra_back)
    b.adjust(1)
    return b.as_markup()


def admin_order_actions_kb(order_id: int, current_status: str, permissions: set[str] | None = None):
    """Inline buttons to advance / cancel an order (role-aware)."""
    perms = permissions or set()
    b = InlineKeyboardBuilder()
    can_change = "orders" in perms
    if can_change and current_status in ORDER_STATUS_FLOW:
        idx = ORDER_STATUS_FLOW.index(current_status)
        if idx + 1 < len(ORDER_STATUS_FLOW):
            nxt = ORDER_STATUS_FLOW[idx + 1]
            b.button(
                text=f"➡️ {STATUS_LABELS[nxt]} ga o'tkazish",
                callback_data=f"admin:order:{order_id}:set:{nxt}",
            )
        if idx > 0:
            prev = ORDER_STATUS_FLOW[idx - 1]
            b.button(
                text=f"⬅️ {STATUS_LABELS[prev]} ga qaytarish",
                callback_data=f"admin:order:{order_id}:set:{prev}",
            )
    if can_change and current_status != "bekor_qilindi":
        b.button(text="❌ Bekor qilish", callback_data=f"admin:order:{order_id}:set:bekor_qilindi")
    b.button(text="✉️ Mijozga javob yozish", callback_data=f"admin:order:{order_id}:reply")
    b.button(text="⬅️ Buyurtmalar ro'yxatiga", callback_data="admin:orders")
    b.button(text="🏠 Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def admin_broadcast_target_kb():
    b = InlineKeyboardBuilder()
    targets = [
        ("start_bosdi", "Start bosgan, kontakt bermagan"),
        ("kontakt_berdi", "Kontakt bergan"),
        ("turni_tanladi", "Turni tanlagan"),
        ("galereyada_toxtadi", "Galereyada to'xtagan"),
        ("mahsulot_tanladi", "Mahsulot tanlagan"),
        ("xomashyoda_toxtadi", "Xomashyoda to'xtagan"),
        ("narxni_kordi", "Narxni ko'rgan"),
        ("buyurtma_berdi", "Buyurtma bergan"),
        ("avans_kutilmoqda", "Avans kutilmoqda"),
        ("jarayonda", "Jarayonda"),
        ("tayyor", "Tayyor"),
        ("yetkazildi", "Yetkazildi"),
        ("tark_etdi", "Tark etgan"),
        ("all", "Barcha foydalanuvchilar"),
    ]
    for tag, label in targets:
        b.button(text=label, callback_data=f"bc:target:{tag}")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def admin_catalog_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🏷 Kategoriyalar", callback_data="cat_admin:categories")
    b.button(text="🖼 Mahsulotlar (rasmlar)", callback_data="cat_admin:products")
    b.button(text="🧵 Xomashyolar", callback_data="cat_admin:materials")
    b.button(text="📐 Razmerlar", callback_data="cat_admin:sizes")
    b.button(text="💲 Narxlar matritsasi", callback_data="cat_admin:prices")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def admin_stats_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📈 Umumiy", callback_data="stats:general")
    b.button(text="📉 Drop-off (bosqichlar bo'yicha)", callback_data="stats:dropoff")
    b.button(text="🏆 Top mahsulotlar", callback_data="stats:top_products")
    b.button(text="📈 Konversiya funnelsi", callback_data="stats:funnel")
    b.button(text="📅 Kunlik hisobot (hozir)", callback_data="stats:daily_now")
    b.button(text="📅 Haftalik hisobot (hozir)", callback_data="stats:weekly_now")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def admin_back_kb(target: str = "admin:panel"):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Orqaga", callback_data=target)
    return b.as_markup()


# ---------- New: Admins management ----------

def admin_admins_list_kb(admins):
    """admins: list[(telegram_id, username, role)]"""
    b = InlineKeyboardBuilder()
    for tg_id, uname, role in admins:
        emoji = {"super_admin": "👑", "operator": "🔧", "moliyachi": "💰"}.get(role, "•")
        b.button(text=f"{emoji} {uname or tg_id} ({role})", callback_data=f"adm:open:{tg_id}")
    b.button(text="➕ Yangi admin qo'shish", callback_data="adm:add")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def admin_role_picker_kb(target_tg_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="👑 super_admin", callback_data=f"adm:set:{target_tg_id}:super_admin")
    b.button(text="🔧 operator", callback_data=f"adm:set:{target_tg_id}:operator")
    b.button(text="💰 moliyachi", callback_data=f"adm:set:{target_tg_id}:moliyachi")
    b.button(text="🗑 O'chirish", callback_data=f"adm:del:{target_tg_id}")
    b.button(text="⬅️ Adminlar ro'yxati", callback_data="admin:admins")
    b.adjust(1)
    return b.as_markup()


# ---------- New: Promo management ----------

def admin_promo_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🎟 Aktiv promokodlar", callback_data="promo:list")
    b.button(text="➕ Yangi promokod", callback_data="promo:add")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def admin_promo_list_kb(promos):
    """promos: list[(id, code, discount_value, discount_type, is_active, uses_count)]"""
    b = InlineKeyboardBuilder()
    for pid, code, val, dtype, active, uses in promos:
        unit = "%" if dtype == "percent" else "so'm"
        status = "✅" if active else "❌"
        b.button(text=f"{status} {code} (-{val}{unit}) [{uses}]", callback_data=f"promo:open:{pid}")
    b.button(text="⬅️ Promokod menu", callback_data="admin:promo")
    b.adjust(1)
    return b.as_markup()


def admin_promo_actions_kb(promo_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="🚫 O'chirish", callback_data=f"promo:del:{promo_id}")
    b.button(text="⏸ Faolsizlantirish", callback_data=f"promo:toggle:{promo_id}")
    b.button(text="⬅️ Promokodlar", callback_data="promo:list")
    b.adjust(1)
    return b.as_markup()


# ---------- New: Reviews ----------

def admin_reviews_kb(reviews):
    """reviews: list[(review_id, order_number, rating, comment, user_tg_id)]"""
    b = InlineKeyboardBuilder()
    for rid, num, rating, comment, tg_id in reviews:
        stars = "⭐" * rating
        text = f"#{num} | {stars} | {(comment or '')[:30]}"
        b.button(text=text, callback_data=f"review:open:{rid}")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


# ---------- New: Settings ----------

def admin_settings_kb(settings: dict[str, str], current_username: str = ""):
    """Render toggle buttons based on current settings."""
    b = InlineKeyboardBuilder()
    uname_str = f" (@{current_username})" if current_username else ""
    b.button(text=f"✏️ Admin username'ini o'zgartirish{uname_str}", callback_data="set:change_admin_username")
    b.button(text="⬅️ Panel", callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


# ---------- New: Confirm delete ----------

def admin_confirm_delete_kb(action: str, target_id: int):
    """action: 'product' | 'category' | 'material' | 'size' | 'promo' | 'admin'"""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=f"confirm_del:{action}:{target_id}")
    b.button(text="❌ Yo'q, bekor qilish", callback_data=f"cancel_del:{action}:{target_id}")
    b.adjust(2)
    return b.as_markup()
