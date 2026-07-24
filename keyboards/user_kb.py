"""All user-facing inline keyboards (+ Reply keyboards for contact/location).

Convention for callback_data (kept short for Telegram's 64-byte limit):
  cancel                       -> cancel any flow
  cat:<id>                     -> pick category
  gnav:<product_id>:<index>    -> gallery navigation
  gsel:<product_id>            -> pick this product
  mat:<material_id>            -> pick material
  size:<size_id>               -> pick size
  cart:add                     -> confirm adding to cart
  cart:redo                    -> choose different material/size
  cart:more                    -> add another product
  cart:done                    -> finish adding -> go to deadline
  cart:view                    -> view cart contents
  cat:restart                  -> restart from category selection
  dl:tez | dl:standard         -> deadline pick
  fin:confirm                  -> final order confirmation
  pay:req:<order_id>           -> ask admin for payment link
  orders:open:<order_id>       -> open one of my orders
  orders:page:<n>              -> orders pagination
  menu:home                    -> back to main menu
  menu:new_order               -> start new order
  menu:my_orders               -> show my orders
  menu:lang                    -> language picker
  lang:<code>                  -> set language
  review:<order_id>:<rating>   -> rate an order (1..5)
  review:skip:<order_id>       -> skip rating
  promo:apply                  -> apply promo code
  promo:skip                   -> skip promo
"""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from utils.i18n import t
from utils.formatting import format_price


# ---------------------------------------------------------------------------
# Reply keyboards (for contact sharing and location)
# ---------------------------------------------------------------------------

def contact_request_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Reply keyboard with a 'send contact' button."""
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(
        text="📱 " + ("Telefon raqamni yuborish" if lang == "uz" else ("Отправить контакт" if lang == "ru" else "Send contact")),
        request_contact=True,
    ))
    b.adjust(1)
    return b.as_markup(resize_keyboard=True, one_time_keyboard=True)


def location_request_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Reply keyboard with a 'send location' button."""
    b = ReplyKeyboardBuilder()
    b.add(KeyboardButton(
        text="📍 " + ("Lokatsiya yuborish" if lang == "uz" else ("Отправить локацию" if lang == "ru" else "Send location")),
        request_location=True,
    ))
    b.add(KeyboardButton(text="✍️ " + ("Manzilni yozib yuborish" if lang == "uz" else ("Введу адрес текстом" if lang == "ru" else "Type address manually"))))
    b.adjust(1, 1)
    return b.as_markup(resize_keyboard=True, one_time_keyboard=True)


def hide_reply_kb() -> ReplyKeyboardMarkup:
    """Empty reply keyboard to hide the previous reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[],
        remove_keyboard=True,
        resize_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Inline keyboards
# ---------------------------------------------------------------------------

def cancel_kb(lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    return b.as_markup()


def category_kb(categories, lang: str = "uz"):
    """categories: list[(id, name)] localized."""
    b = InlineKeyboardBuilder()
    for cid, name in categories:
        b.button(text=name, callback_data=f"cat:{cid}")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def gallery_album_kb(page_items: list[tuple[int, int, str]], page: int, total_pages: int, lang: str = "uz"):
    """page_items: list[(product_id, item_num, name)]"""
    b = InlineKeyboardBuilder()
    for pid, num, name in page_items:
        b.button(
            text=f"✅ #{num} - Kartinani tanlash",
            callback_data=f"gsel:{pid}",
        )
    b.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi 4 ta", callback_data=f"gpage:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📊 {page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi 4 ta ➡️", callback_data=f"gpage:{page + 1}"))
    if nav:
        b.row(*nav)

    b.row(InlineKeyboardButton(text="🖼 " + ("Boshqa bo'lim" if lang=="uz" else ("Другая категория" if lang=="ru" else "Other category")), callback_data="cat:restart"))
    b.row(InlineKeyboardButton(text=t(lang, "cancel"), callback_data="cancel"))
    return b.as_markup()


def gallery_kb(product_id: int, index: int, total: int, lang: str = "uz"):
    b = InlineKeyboardBuilder()
    if index > 0:
        b.button(text="⬅️ " + ("Oldingisi" if lang=="uz" else ("Предыдущий" if lang=="ru" else "Prev")), callback_data=f"gnav:{product_id}:{index - 1}")
    if index + 1 < total:
        b.button(text=("Keyingisi" if lang=="uz" else ("Следующий" if lang=="ru" else "Next")) + " ➡️", callback_data=f"gnav:{product_id}:{index + 1}")
    b.button(text="✅ " + ("Shu kartinani tanlayman" if lang=="uz" else ("Выбираю этот" if lang=="ru" else "Select this")), callback_data=f"gsel:{product_id}")
    b.button(text="🖼 " + ("Boshqa bo'limni tanlash" if lang=="uz" else ("Другая категория" if lang=="ru" else "Other category")), callback_data="cat:restart")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    if index > 0 and index + 1 < total:
        b.adjust(2, 1, 1, 1)
    else:
        b.adjust(1, 1, 1, 1)
    return b.as_markup()


def materials_kb(materials, lang: str = "uz"):
    """materials: list[(id, name)] localized."""
    b = InlineKeyboardBuilder()
    for mid, name in materials:
        b.button(text=name, callback_data=f"mat:{mid}")
    b.button(text=t(lang, "back"), callback_data="back:gallery")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def sizes_kb(sizes, lang: str = "uz"):
    """sizes: list[(id, name, price)] localized."""
    b = InlineKeyboardBuilder()
    for item in sizes:
        if len(item) == 3:
            sid, name, price_str = item
            btn_text = f"📐 {name} — {price_str} so'm"
        else:
            sid, name = item
            btn_text = f"📐 {name}"
        b.button(text=btn_text, callback_data=f"size:{sid}")
    custom_label = (
        "✍️ Boshqa o'lcham (Custom)" if lang == "uz" else
        ("✍️ Другой размер (Custom)" if lang == "ru" else "✍️ Custom size")
    )
    b.button(text=custom_label, callback_data="size:custom")
    b.button(text=t(lang, "back"), callback_data="back:material")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def confirm_item_kb(lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text="🚀 " + ("Buyurtma berish (Rasmiylashtirish)" if lang=="uz" else ("Оформить заказ" if lang=="ru" else "Checkout")), callback_data="cart:done")
    b.button(text="➕ " + ("Yana kartinka qo'shish" if lang=="uz" else ("Добавить ещё" if lang=="ru" else "Add more")), callback_data="cart:more")
    b.button(text="🔄 " + ("O'lcham yoki matoni o'zgartirish" if lang=="uz" else ("Изменить размер/материал" if lang=="ru" else "Change size/material")), callback_data="cart:redo")
    b.adjust(1)
    return b.as_markup()


def more_items_kb(lang: str = "uz", cart_summary: str | None = None):
    b = InlineKeyboardBuilder()
    b.button(text="➕ " + ("Yana kartinka qo'shish" if lang=="uz" else ("Добавить ещё" if lang=="ru" else "Add more")), callback_data="cart:more")
    b.button(text="🖼 " + ("Boshqa bo'limga o'tish" if lang=="uz" else ("Другая категория" if lang=="ru" else "Other category")), callback_data="cat:restart")
    b.button(text="🛒 " + ("Savatni ko'rish" if lang=="uz" else ("Просмотреть корзину" if lang=="ru" else "View cart")), callback_data="cart:view")
    b.button(text="🚀 " + ("Buyurtmani rasmiylashtirish" if lang=="uz" else ("Оформить заказ" if lang=="ru" else "Checkout")), callback_data="cart:done")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def cart_view_kb(lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text="➕ " + ("Yana kartinka qo'shish" if lang=="uz" else ("Добавить ещё" if lang=="ru" else "Add more")), callback_data="cart:more")
    b.button(text="🚀 " + ("Buyurtmani rasmiylashtirish" if lang=="uz" else ("Оформить заказ" if lang=="ru" else "Checkout")), callback_data="cart:done")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def deadline_kb(lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "deadline_fast"), callback_data="dl:tez")
    b.button(text=t(lang, "deadline_standard"), callback_data="dl:standard")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def promo_kb(lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text="🎟 " + ("Promokod kiritish" if lang=="uz" else ("Ввести промокод" if lang=="ru" else "Enter promo")), callback_data="promo:apply")
    b.button(text="➡️ " + ("Promokodsiz davom etish" if lang=="uz" else ("Продолжить без промокода" if lang=="ru" else "Skip promo")), callback_data="promo:skip")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def final_confirm_kb(lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text="✅ " + ("Buyurtmani tasdiqlash" if lang=="uz" else ("Подтвердить заказ" if lang=="ru" else "Confirm order")), callback_data="fin:confirm")
    b.button(text=t(lang, "cancel"), callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


def pay_request_kb(order_id: int, order_number: str = "", admin_username: str = "", user_id: int = 0, lang: str = "uz"):
    b = InlineKeyboardBuilder()
    if admin_username:
        clean_user = admin_username.lstrip("@")
        msg_text = (
            f"Assalomu alaykum! Men #{order_number} sonli buyurtmam bo'yicha bog'lanmoqchiman. (ID: {user_id})"
            if lang == "uz" else
            (f"Здравствуйте! Я обращаюсь по поводу заказа #{order_number}. (ID: {user_id})" if lang == "ru" else f"Hello! I am contacting about order #{order_number}. (ID: {user_id})")
        )
        import urllib.parse
        link = f"https://t.me/{clean_user}?text={urllib.parse.quote(msg_text)}"
        b.button(
            text="💬 " + ("Admin bilan bog'lanish" if lang == "uz" else ("Связаться с админом" if lang == "ru" else "Contact Admin")),
            url=link,
        )
    b.button(text="🏠 " + ("Bosh menyu" if lang == "uz" else ("Главное меню" if lang == "ru" else "Main menu")), callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def main_menu_kb(is_admin: bool = False, lang: str = "uz"):
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "menu_new_order"), callback_data="menu:new_order")
    b.button(text=t(lang, "menu_my_orders"), callback_data="menu:my_orders")
    b.button(text=t(lang, "menu_change_lang"), callback_data="menu:lang")
    if is_admin:
        b.button(text=t(lang, "admin_panel_title").split("\n")[0].replace("<b>", "").replace("</b>", ""),
                 callback_data="admin:panel")
    b.adjust(1)
    return b.as_markup()


def language_picker_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🇺🇿 O'zbekcha", callback_data="lang:uz")
    b.button(text="🇷🇺 Русский", callback_data="lang:ru")
    b.button(text="🇬🇧 English", callback_data="lang:en")
    b.adjust(1)
    return b.as_markup()


def orders_list_kb(orders, page: int = 0, per_page: int = 5, total: int = 0, lang: str = "uz"):
    """orders: list[(order_id, order_number, status, total_price, created_at)] for current page."""
    b = InlineKeyboardBuilder()
    if not orders:
        b.button(text=t(lang, "no_orders"), callback_data="noop")
    for oid, num, status, price, created in orders:
        label = f"#{num}  |  {format_price(price)} so'm  |  {_status_emoji(status)} {_short_status(status, lang)}"
        b.button(text=label, callback_data=f"orders:open:{oid}")
    total_pages = max(1, (total + per_page - 1) // per_page)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"orders:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"orders:page:{page + 1}"))
    if nav:
        b.row(*nav)
    b.button(text="🏠 " + ("Bosh menyu" if lang=="uz" else ("Главное меню" if lang=="ru" else "Main menu")), callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def review_kb(order_id: int, lang: str = "uz"):
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐" * i, callback_data=f"review:{order_id}:{i}")
    b.button(text=t(lang, "cancel"), callback_data=f"review:skip:{order_id}")
    b.adjust(5, 1)
    return b.as_markup()


def _status_emoji(status: str) -> str:
    return {
        "draft": "📝",
        "yangi": "🆕",
        "avans_kutilmoqda": "💳",
        "jarayonda": "🔧",
        "tayyor": "✅",
        "yetkazildi": "📦",
        "bekor_qilindi": "❌",
        "tark_etdi": "🚪",
    }.get(status, "•")


def _short_status(status: str, lang: str) -> str:
    key = {
        "draft": "status_draft",
        "yangi": "status_new",
        "avans_kutilmoqda": "status_avans",
        "jarayonda": "status_progress",
        "tayyor": "status_ready",
        "yetkazildi": "status_delivered",
        "bekor_qilindi": "status_cancelled",
        "tark_etdi": "status_left",
    }.get(status, "status_new")
    return t(lang, key)
