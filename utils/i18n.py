"""Internationalization (i18n) — Uzbek / Russian / English.

Usage in handlers:
    lang = await get_user_language(telegram_id)
    text = t(lang, "welcome", name="Aziz")
"""
from __future__ import annotations

from sqlalchemy import select, update

from database.db import async_session
from database.models import User

LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANG = "uz"

_STRINGS: dict[str, dict[str, str]] = {
    # ---------- Common ----------
    "cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена", "en": "❌ Cancel"},
    "back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"},
    "yes": {"uz": "✅ Ha", "ru": "✅ Да", "en": "✅ Yes"},
    "no": {"uz": "❌ Yo'q", "ru": "❌ Нет", "en": "❌ No"},
    "noop": {"uz": "—", "ru": "—", "en": "—"},

    # ---------- Onboarding ----------
    "welcome_lang": {
        "uz": "🌐 <b>Muloqot tilini tanlang / Выберите язык / Select language:</b>",
        "ru": "🌐 <b>Выберите язык / Select language / Muloqot tilini tanlang:</b>",
        "en": "🌐 <b>Select language / Muloqot tilini tanlang / Выберите язык:</b>",
    },
    "welcome_new": {
        "uz": "👋 <b>Assalomu alaykum!</b>\n\nKartinalar buyurtma qilish botiga xush kelibsiz! ✨\nBuyurtmani rasmiylashtirish uchun ro'yxatdan o'ting.\n\n✏️ <b>Ism va familiyangizni kiriting:</b>",
        "ru": "👋 <b>Здравствуйте!</b>\n\nДобро пожаловать в бот заказа картин! ✨\nДля оформления заказа просим пройти регистрацию.\n\n✏️ <b>Введите ваше имя и фамилию:</b>",
        "en": "👋 <b>Hello!</b>\n\nWelcome to the canvas ordering bot! ✨\nPlease register to place an order.\n\n✏️ <b>Enter your full name:</b>",
    },
    "welcome_back": {
        "uz": "👋 Assalomu alaykum, {name}!\n\nQuyidagi menyudan kerakli bo'limni tanlang:",
        "ru": "👋 Здравствуйте, {name}!\n\nВыберите нужный раздел меню:",
        "en": "👋 Hello, {name}!\n\nChoose an option from the menu:",
    },
    "name_invalid": {
        "uz": "❌ Ism juda qisqa kiritildi. Kamida 2 ta harfdan iborat bo'lishi kerak.\nQaytadan kiriting:",
        "ru": "❌ Имя введено неверно. Минимум 2 буквы.\nВведите снова:",
        "en": "❌ Invalid name. At least 2 letters required.\nTry again:",
    },
    "ask_phone": {
        "uz": "📞 <b>Telefon raqamingizni yuboring:</b>\n\nPastdagi «📱 Telefon raqamni yuborish» tugmasini bosing yoki raqamingizni yozib yuboring (Masalan: +998901234567).",
        "ru": "📞 <b>Отправьте ваш номер телефона:</b>\n\nНажмите кнопку «📱 Отправить контакт» ниже или введите номер вручную (Например: +998901234567).",
        "en": "📞 <b>Send your phone number:</b>\n\nPress the «📱 Send contact» button below or type your number (Example: +998901234567).",
    },
    "phone_invalid": {
        "uz": "❌ Telefon raqami noto'g'ri kiritildi.\nIltimos, to'g'ri raqam kiriting (Masalan: +998901234567) yoki pastdagi tugmadan foydalaning:",
        "ru": "❌ Неверный формат номера телефона.\nВведите правильный номер (Например: +998901234567) или используйте кнопку ниже:",
        "en": "❌ Invalid phone format.\nEnter a valid number (Example: +998901234567) or use the button below:",
    },
    "ask_address": {
        "uz": "🏠 <b>Yetkazib berish manzilini kiriting:</b>\n\nShahar, tuman va ko'changizni yozing yoki pastdagi «📍 Lokatsiya yuborish» tugmasini bosing:",
        "ru": "🏠 <b>Введите адрес доставки:</b>\n\nУкажите город, район и улицу или нажмите кнопку «📍 Отправить локацию» ниже:",
        "en": "🏠 <b>Enter delivery address:</b>\n\nType your city, district and street or click «📍 Send location» below:",
    },
    "ask_address_prompt": {
        "uz": "✍️ <b>Yetkazib berish manzilini matn shaklida yozib yuboring:</b>\n\n(Masalan: Toshkent sh., Chilonzor tuman, 14-mavze, 25-uy)",
        "ru": "✍️ <b>Введите адрес доставки текстом:</b>\n\n(Например: г. Ташкент, Чиланзарский р-н, 14-квартал, д. 25)",
        "en": "✍️ <b>Type your delivery address:</b>\n\n(Example: Tashkent, Chilanzar dist., block 14, house 25)",
    },
    "address_invalid": {
        "uz": "❌ Manzil juda qisqa kiritildi.\nIltimos, aniqroq manzil kiriting (kamida 5 ta belgi):",
        "ru": "❌ Слишком короткий адрес.\nПожалуйста, введите полный адрес (минимум 5 символов):",
        "en": "❌ Address too short.\nPlease enter a detailed address (at least 5 chars):",
    },
    "cancelled": {
        "uz": "❌ Buyurtma jarayoni bekor qilindi.\nYangi buyurtma berish uchun /start bosing.",
        "ru": "❌ Оформление заказа отменено.\nНажмите /start, чтобы начать заново.",
        "en": "❌ Order creation cancelled.\nPress /start to try again.",
    },

    # ---------- Main menu ----------
    "menu_new_order": {"uz": "🛒 Yangi buyurtma", "ru": "🛒 Новый заказ", "en": "🛒 New order"},
    "menu_my_orders": {"uz": "📦 Buyurtmalarim", "ru": "📦 Мои заказы", "en": "📦 My orders"},
    "menu_change_lang": {"uz": "🌐 Til tanlash", "ru": "🌐 Выбор языка", "en": "🌐 Change language"},
    "menu_help": {"uz": "ℹ️ Yordam", "ru": "ℹ️ Помощь", "en": "ℹ️ Help"},

    # ---------- Order flow ----------
    "pick_category": {
        "uz": "🖼 <b>Qaysi turdagi kartinani tanlaysiz?</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        "ru": "🖼 <b>Какую категорию картин вы выбираете?</b>\n\nВыберите раздел из списка:",
        "en": "🖼 <b>Which category of canvas do you prefer?</b>\n\nSelect a section from below:",
    },
    "gallery_caption": {
        "uz": "🖼 <b>Mahsulot {idx}/{total}</b>\n\n{caption}",
        "ru": "🖼 <b>Товар {idx}/{total}</b>\n\n{caption}",
        "en": "🖼 <b>Product {idx}/{total}</b>\n\n{caption}",
    },
    "gallery_empty": {
        "uz": "Hozircha ushbu bo'limda mahsulotlar mavjud emas. Iltimos, boshqa bo'limni tanlang.",
        "ru": "В этой категории пока нет товаров. Пожалуйста, выберите другую категорию.",
        "en": "No products in this category yet. Please select another category.",
    },
    "pick_material": {"uz": "🧵 <b>Kartinka matosini (material) tanlang:</b>", "ru": "🧵 <b>Выберите материал холста:</b>", "en": "🧵 <b>Choose material:</b>"},
    "pick_size": {"uz": "📐 <b>Kartinka o'lchamini tanlang:</b>", "ru": "📐 <b>Выберите размер картины:</b>", "en": "📐 <b>Choose size:</b>"},
    "price_label": {
        "uz": "💵 <b>Tanlangan mahsulot narxi:</b>\n\n🖼 <b>Mahsulot:</b> {product}\n💰 <b>Narxi:</b> <b>{price} so'm</b>\n\nUshbu tanlovni savatga qo'shasizmi?",
        "ru": "💵 <b>Стоимость выбранного товара:</b>\n\n🖼 <b>Товар:</b> {product}\n💰 <b>Цена:</b> <b>{price} сум</b>\n\nДобавить товар в корзину?",
        "en": "💵 <b>Price:</b>\n\n🖼 <b>Product:</b> {product}\n💰 <b>Price:</b> <b>{price} UZS</b>\n\nAdd this item to cart?",
    },
    "cart_added": {
        "uz": "✅ <b>Mahsulot savatga qo'shildi!</b>\n\nYana boshqa kartinka qo'shasizmi yoki buyurtmani rasmiylashtirasizmi?",
        "ru": "✅ <b>Товар успешно добавлен в корзину!</b>\n\nЖелаете добавить ещё товар или оформить заказ?",
        "en": "✅ <b>Product added to cart!</b>\n\nWould you like to add another item or complete the order?",
    },
    "cart_view": {
        "uz": "🛒 <b>Sizning savatingiz:</b>\n\n{items}\n\n💰 <b>Jami summa:</b> <b>{total} so'm</b>",
        "ru": "🛒 <b>Ваша корзина:</b>\n\n{items}\n\n💰 <b>Итого к оплате:</b> <b>{total} сум</b>",
        "en": "🛒 <b>Your Cart:</b>\n\n{items}\n\n💰 <b>Total Amount:</b> <b>{total} UZS</b>",
    },
    "pick_deadline": {
        "uz": "⏱ <b>Buyurtmani tayyorlash muddatini tanlang:</b>",
        "ru": "⏱ <b>Выберите срок изготовления заказа:</b>",
        "en": "⏱ <b>Choose estimated lead time:</b>",
    },
    "deadline_fast": {"uz": "⚡ Shoshilinch (1 hafta ichida)", "ru": "⚡ Срочно (в течение 1 недели)", "en": "⚡ Urgent (within 1 week)"},
    "deadline_standard": {"uz": "🕐 Standart (15 kun ichida)", "ru": "🕐 Стандарт (в течение 15 дней)", "en": "🕐 Standard (within 15 days)"},
    "order_placed": {
        "uz": "🎉 <b>Buyurtmangiz muvaffaqiyatli qabul qilindi!</b>\n\n🧾 <b>Buyurtma raqami:</b> <b>#{num}</b>\n\n✨ Rahmat! Operatormiz tez orada siz bilan bog'lanib, buyurtma tafsilotlarini tasdiqlaydi.",
        "ru": "🎉 <b>Ваш заказ успешно принят!</b>\n\n🧾 <b>Номер заказа:</b> <b>#{num}</b>\n\n✨ Спасибо! Наш оператор свяжется с вами в ближайшее время для подтверждения деталей заказа.",
        "en": "🎉 <b>Your order has been placed successfully!</b>\n\n🧾 <b>Order #:</b> <b>#{num}</b>\n\n✨ Thank you! Our representative will contact you shortly to confirm your order.",
    },
    "pay_request_sent": {
        "uz": "✅ <b>Adminga to'lov so'rovi yuborildi!</b>\n\nSizning ID: <code>{tg_id}</code>\nBuyurtma raqami: <b>#{num}</b>\n\nTez orada admin siz bilan bog'lanadi.",
        "ru": "✅ <b>Запрос на оплату отправлен администратору!</b>\n\nВаш ID: <code>{tg_id}</code>\nНомер заказа: <b>#{num}</b>\n\nАдминистратор свяжется с вами в ближайшее время.",
        "en": "✅ <b>Payment request sent to admin!</b>\n\nYour ID: <code>{tg_id}</code>\nOrder #: <b>#{num}</b>\n\nAdmin will contact you shortly.",
    },
    "pay_request_btn": {"uz": "💬 Admin bilan bog'lanish", "ru": "💬 Связаться с админом", "en": "💬 Contact Admin"},
    "pay_request_cooldown": {
        "uz": "⏳ So'rovingiz allaqachon yuborilgan. Iltimos, admin javobini kuting.",
        "ru": "⏳ Ваш запрос уже отправлен. Пожалуйста, ожидайте ответа администратора.",
        "en": "⏳ Request already sent. Please wait for admin's response.",
    },

    # ---------- Status updates ----------
    "status_new": {"uz": "Yangi", "ru": "Новый", "en": "New"},
    "status_progress": {"uz": "Jarayonda", "ru": "В работе", "en": "In progress"},
    "status_ready": {"uz": "Tayyor", "ru": "Готов", "en": "Ready"},
    "status_delivered": {"uz": "Yetkazildi", "ru": "Доставлен", "en": "Delivered"},
    "status_cancelled": {"uz": "Bekor qilindi", "ru": "Отменён", "en": "Cancelled"},
    "status_draft": {"uz": "Qoralama", "ru": "Черновик", "en": "Draft"},
    "status_left": {"uz": "Tark etdi", "ru": "Покинул", "en": "Abandoned"},

    "status_changed": {
        "uz": "📦 <b>Buyurtmangiz #{num} holati o'zgardi:</b>\n\n➡️ <b>{label}</b>\n\nSavollaringiz bo'lsa, admin: @{admin}",
        "ru": "📦 <b>Статус вашего заказа #{num} изменён:</b>\n\n➡️ <b>{label}</b>\n\nПо всем вопросам: @{admin}",
        "en": "📦 <b>Status of order #{num} has updated:</b>\n\n➡️ <b>{label}</b>\n\nContact admin: @{admin}",
    },

    # ---------- My orders ----------
    "my_orders_title": {"uz": "📦 <b>Mening buyurtmalarim ({total} ta):</b>", "ru": "📦 <b>Мои заказы ({total}):</b>", "en": "📦 <b>My orders ({total}):</b>"},
    "no_orders": {"uz": "(buyurtmalar mavjud emas)", "ru": "(нет заказов)", "en": "(no orders)"},

    # ---------- Admin panel ----------
    "admin_panel_title": {
        "uz": "🔧 <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
        "ru": "🔧 <b>Админ-панель</b>\n\nВыберите раздел:",
        "en": "🔧 <b>Admin panel</b>\n\nChoose section:",
    },
    "admin_orders": {"uz": "📦 Buyurtmalar", "ru": "📦 Заказы", "en": "📦 Orders"},
    "admin_users": {"uz": "👥 Foydalanuvchilar", "ru": "👥 Пользователи", "en": "👥 Users"},
    "admin_broadcast": {"uz": "📢 Xabar yuborish", "ru": "📢 Рассылка", "en": "📢 Broadcast"},
    "admin_catalog": {"uz": "🛠 Katalog", "ru": "🛠 Каталог", "en": "🛠 Catalog"},
    "admin_stats": {"uz": "📊 Statistika", "ru": "📊 Статистика", "en": "📊 Stats"},
    "admin_export": {"uz": "📋 Excel eksport", "ru": "📋 Экспорт Excel", "en": "📋 Excel export"},
    "admin_settings": {"uz": "⚙️ Sozlamalar", "ru": "⚙️ Настройки", "en": "⚙️ Settings"},
    "admin_admins": {"uz": "👮 Adminlar", "ru": "👮 Администраторы", "en": "👮 Admins"},
    "admin_promo": {"uz": "🎟 Promokodlar", "ru": "🎟 Промокоды", "en": "🎟 Promocodes"},
    "admin_reviews": {"uz": "⭐ Sharhlar", "ru": "⭐ Отзывы", "en": "⭐ Reviews"},
    "admin_close": {"uz": "🚪 Yopish", "ru": "🚪 Закрыть", "en": "🚪 Close"},

    # ---------- Language picker ----------
    "lang_picker_title": {
        "uz": "🌐 <b>Muloqot tilini tanlang:</b>",
        "ru": "🌐 <b>Выберите язык общения:</b>",
        "en": "🌐 <b>Select your preferred language:</b>",
    },
    "lang_uz": {"uz": "🇺🇿 O'zbekcha", "ru": "🇺🇿 Узбекский", "en": "🇺🇿 Uzbek"},
    "lang_ru": {"uz": "🇷🇺 Русский", "ru": "🇷🇺 Русский", "en": "🇷🇺 Russian"},
    "lang_en": {"uz": "🇬🇧 English", "ru": "🇬🇧 Английский", "en": "🇬🇧 English"},
    "lang_set": {
        "uz": "✅ <b>Muloqot tili o'zgartirildi: O'zbekcha</b>",
        "ru": "✅ <b>Язык успешно изменён: Русский</b>",
        "en": "✅ <b>Language changed: English</b>",
    },

    # ---------- Review ----------
    "review_ask": {
        "uz": "⭐ <b>#{num} sonli buyurtmangiz yetkazildi!</b>\n\nIltimos, mahsulotimiz sifatini baholang:",
        "ru": "⭐ <b>Ваш заказ #{num} доставлен!</b>\n\nПожалуйста, оцените качество товара:",
        "en": "⭐ <b>Your order #{num} has been delivered!</b>\n\nPlease rate product quality:",
    },
    "review_thanks": {
        "uz": "✅ <b>Rahmat! Bahoingiz qabul qilindi.</b>",
        "ru": "✅ <b>Спасибо! Ваша оценка принята.</b>",
        "en": "✅ <b>Thank you! Your feedback has been recorded.</b>",
    },
    "review_already": {
        "uz": "Siz ushbu buyurtmaga allaqachon baho bergansiz.",
        "ru": "Вы уже оценили этот заказ.",
        "en": "You have already rated this order.",
    },
    "review_ask_comment": {
        "uz": "💬 <b>Izoh qoldirishingiz mumkin (yoki o'tkazib yuborish uchun «-» deb yozing):</b>",
        "ru": "💬 <b>Вы можете оставить отзыв (или введите «-» для пропуска):</b>",
        "en": "💬 <b>You can leave a comment (or send «-» to skip):</b>",
    },

    # ---------- Promo ----------
    "promo_ask_code": {
        "uz": "🎟 **Promokod bo'lsa kiriting (yoki promosiz davom etish uchun «-» yuboring):**",
        "ru": "🎟 **Введите промокод (или отправьте «-» для продолжения без скидки):**",
        "en": "🎟 **Enter promo code (or send «-» to proceed without discount):**",
    },
    "promo_invalid": {
        "uz": "❌ Promokod noto'g'ri kiritildi yoki muddati tugagan.",
        "ru": "❌ Промокод недействителен или срок его действия истёк.",
        "en": "❌ Invalid or expired promo code.",
    },
    "promo_applied": {
        "uz": "✅ **Promokod qo'llandi! Chegirma:** <b>{discount} so'm</b>",
        "ru": "✅ **Промокод применён! Скидка:** <b>{discount} сум</b>",
        "en": "✅ **Promo code applied! Discount:** <b>{discount} UZS</b>",
    },
    "promo_skip": {
        "uz": "Promokodsiz davom etamiz.",
        "ru": "Продолжаем без промокода.",
        "en": "Continuing without promo code.",
    },
    "promo_already_used": {
        "uz": "❌ Siz ushbu promokodni allaqachon ishlatgansiz.",
        "ru": "❌ Вы уже использовали этот промокод.",
        "en": "❌ You have already used this promo code.",
    },

    # ---------- Generic error ----------
    "error_generic": {
        "uz": "❌ Kechirasiz, kutilmagan xatolik yuz berdi. Qaytadan boshlash uchun: /start",
        "ru": "❌ Извините, произошла ошибка. Для перезапуска нажмите: /start",
        "en": "❌ Sorry, an error occurred. To restart, tap: /start",
    },
}


def t(lang: str, key: str, **kw) -> str:
    """Translate a key into the given language with optional format args."""
    lang = lang if lang in LANGUAGES else DEFAULT_LANG
    entry = _STRINGS.get(key)
    if entry is None:
        return key  # graceful fallback
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kw:
        try:
            return text.format(**kw)
        except Exception:
            return text
    return text


async def get_user_language(telegram_id: int) -> str:
    """Fetch user's preferred language from DB."""
    async with async_session() as s:
        lang = (
            await s.execute(
                select(User.language).where(User.telegram_id == telegram_id)
            )
        ).scalar_one_or_none()
    return lang if lang in LANGUAGES else DEFAULT_LANG


async def set_user_language(telegram_id: int, lang: str) -> None:
    if lang not in LANGUAGES:
        return
    async with async_session() as s:
        await s.execute(
            update(User).where(User.telegram_id == telegram_id).values(language=lang)
        )
        await s.commit()


async def get_entity_name(obj, lang: str, default_lang: str = DEFAULT_LANG) -> str:
    """Get localized name from a Category/Material/Size/Product instance."""
    if obj is None:
        return "-"
    for attr in (f"name_{lang}", f"caption_{lang}"):
        val = getattr(obj, attr, None)
        if val:
            return val
    # Fallbacks
    for attr in ("name_uz", "caption_uz", "name_ru", "caption_ru", "name_en", "caption_en"):
        val = getattr(obj, attr, None)
        if val:
            return val
    return "-"
