# Kartinka (holst) buyurtma Telegram bot v2

Aiogram 3.x + SQLAlchemy 2.0 (async) + APScheduler asosida yozilgan bot.

## ✨ v2 da qo'shilgan imkoniyatlar

### 🌐 Ko'p tillilik (i18n)
- 3 ta til: **O'zbekcha 🇺🇿 / Русский 🇷🇺 / English 🇬🇧**
- Foydalanuvchi tilni o'zi tanlaydi (menyuda "🌐 Til tanlash")
- Kategoriya, xomashyo, razmer, mahsulot nomlari ham ko'p tilli
- Barcha tugmalar va xabarlar tanlangan tilda

### 👮 Admin rollari (role-based access)
- **super_admin** — to'liq huquq (panel + broadcast + sozlamalar + adminlar + katalog + promo + statistika + eksport)
- **operator** — buyurtmalar + katalog + statistika + promo
- **moliyachi** — buyurtmalar + statistika + eksport + promo
- Rollarni faqat super_admin o'zgartira oladi
- Admin qo'shish/o'chirish faqat super_admin huquqi

### ⭐ Mijoz baholash (review)
- Buyurtma "yetkazildi" bo'lganda mijozga 1-5 yulduz baholash so'rovi boradi
- Izoh qoldirishi mumkin (ixtiyoriy)
- Baholar **faqat adminga ko'rinadi** (mijozlar boshqalarning bahosini ko'rmaydi)
- Statistikada o'rtacha baho ko'rinadi

### 🎟 Promokodlar va chegirmalar
- Admin promo yaratsa: `percent` (foiz) yoki `fixed` (so'm) chegirma
- Min buyurtma summasi, max foydalanish soni, amal qilish muddati
- Bir foydalanuvchi bir promokodni faqat bir marta ishlata oladi
- Mijoz buyurtma yakunlashdan oldin promokod kiritadi

### 🔒 Xavfsizlik yaxshilanishlari
- **Stale draft cleanup** — yangi buyurtma boshlashdan oldin eski savat o'chiriladi
- **Payment request spam protection** — bir buyurtma uchun 5 daqiqada 1 marta (sozlanadi)
- **Confirm-before-delete** — katalogdan o'chirishda tasdiqlash so'raladi
- **Tag history** — har bir tag o'zgarishi `user_tag_history` jadvaliga yoziladi (funnel statistikasi uchun)
- **Timezone-aware datetime** — `datetime.utcnow()` o'rniga `datetime.now(timezone.utc)`
- **Scheduler tz Asia/Tashkent** — kunlik hisobot 21:00 Toshkent vaqtida
- **Bot.get_current()** — circular import xavfi yo'q

### 📊 Statistika yaxshilanishlari
- **Konversiya funnelsi** — bosqichlar bo'yicha (start → kontakt → tur → mahsulot → narx → buyurtma → yetkazildi)
- **O'rtacha baho** statistikasi
- **Excel eksport 7 varaq** bilan (Orders, Items, Users, Dropoff, Broadcasts, Reviews, Promos)

### 🎨 Mijoz oqimi yaxshilanishlari
- **📱 Kontakt yuborish tugmasi** — telefon raqamni tugma bilan yuborish
- **📍 Lokatsiya yuborish tugmasi** — manzilni Telegram lokatsiya sifatida yuborish
- **🛒 Savat ko'rinishi** — "Savatni ko'rish" tugmasi, har qo'shilgandan keyin savat mazmuni ko'rinadi
- **Buyurtmalarim ro'yxati** — narx, sana, status bilan (faqat raqam emas)
- **Til tanlash** menyuda doimiy

### 🛠 Admin oqimi yaxshilanishlari
- **Ism/telefon/username bo'yicha qidirish** (faqat ID emas)
- **Mahsulot tartibini o'zgartirish** (⬆️⬇️ tugmalar)
- **Mahsulotni faolsizlantirish** (o'chirmasdan)
- **O'chirishda tasdiqlash** so'raladi
- **Broadcast bloklaganlar ro'yxati** — kim bloklagani aniq ko'rinadi
- **Sozlamalar toggle** — "yangi mijoz haqida xabar", "drop-off haqida xabar"

## Texnologik stack
- Python 3.11+
- aiogram 3.x
- SQLAlchemy 2.0 (async) + aiosqlite (PostgreSQL ga o'tish oson)
- APScheduler
- python-dotenv
- openpyxl (Excel eksport uchun)

## O'rnatish

```bash
cd bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env faylini to'ldiring:
#   BOT_TOKEN=...        (BotFather dan)
#   ADMIN_IDS=123456789  (sizning Telegram ID ngiz)
#   ADMIN_USERNAME=admin (sizning username)
python main.py
```

## Admin panelga kirish

1. `.env` dagi `ADMIN_IDS` ga o'z Telegram ID ngizni qo'shing
2. Botga `/admin` yuboring yoki "🔧 Admin panel" tugmasini bosing
3. Admin bo'lmaganlar uchun bu komanda/tugma **ko'rinmaydi va javob bermaydi**

## Fayl strukturasi

```
bot/
├── main.py                        # Botni ishga tushiruvchi
├── config.py                      # Konfiguratsiya (.env dan)
├── requirements.txt
├── .env.example
├── database/
│   ├── models.py                  # SQLAlchemy modellari (12 jadval)
│   └── db.py                      # Engine, session, init, seed
├── states/order_states.py         # FSM holatlari
├── utils/
│   ├── validators.py              # Ism/telefon/manzil tekshiruvi
│   ├── security.py                # IsAdminFilter, role-based access
│   ├── formatting.py              # Narx, buyurtma formati
│   ├── state_helpers.py           # Tag history bilan sync
│   └── i18n.py                    # 3 til tarjimalari
├── middlewares/
│   ├── flood_control.py           # Anti-spam
│   └── state_sync.py              # last_active_at + tark_etdi reactivation
├── keyboards/
│   ├── user_kb.py                 # User inline + reply tugmalar
│   └── admin_kb.py                # Admin inline tugmalar
├── handlers/
│   ├── user/
│   │   ├── start.py               # Ro'yxat + menyu + til + cancel
│   │   ├── gallery.py             # Galereya (multilingual)
│   │   ├── order_flow.py          # To'liq buyurtma + promo + review
│   │   └── my_orders.py           # Mening buyurtmalarim
│   └── admin/
│       ├── panel.py               # Panel + sozlamalar
│       ├── orders_management.py   # Buyurtmalar (qidirish bilan)
│       ├── broadcast.py           # Ommaviy xabar
│       ├── reports.py             # Statistika + Excel
│       ├── catalog.py             # Katalog CRUD
│       ├── admins.py              # Admin rollari
│       ├── promos.py              # Promokodlar
│       └── reviews.py             # Sharhlar ko'rish
├── services/
│   ├── notifications.py           # Admin/mijoz bildirishnomalari
│   ├── reports.py                 # Hisobot generatorlari
│   └── reminders.py               # APScheduler jobs (tz-aware)
├── logs/
└── README.md
```

## Ma'lumotlar bazasi jadvallari (12 ta)

1. **users** — telegram_id, username, full_name, phone, address, tag, language, reminder_sent
2. **categories** — name_uz/ru/en
3. **products** — photo_file_id, caption_uz/ru/en, order_index, is_active
4. **materials** — name_uz/ru/en
5. **sizes** — name_uz/ru/en
6. **price_matrix** — (material_id, size_id, price)
7. **orders** — order_number, status, total_price, discount, promo_code, deadline_type
8. **order_items** — product/material/size/price
9. **broadcasts_log** — admin_id, target, sent/failed/blocked
10. **admin_users** — telegram_id, role (super_admin/operator/moliyachi)
11. **reviews** — order_id, rating (1-5), comment
12. **promo_codes** — code, discount_type, discount_value, valid_until
13. **promo_usages** — (user_id, promo_id) unique
14. **user_tag_history** — drop-off funnel uchun
15. **bot_settings** — toggle settings (notify_new_user, notify_dropoff)
16. **payment_request_log** — spam protection uchun

## PostgreSQL ga o'tish

`.env` da:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
```
`requirements.txt` ga `asyncpg` qo'shing. Kodda boshqa o'zgarish kerak emas.

## Sinovdan o'tgan flow lar (simulyatsiya)

✅ Mijoz ro'yxatdan o'tish (ism/telefon/manzil)
✅ Telefon tugmasi bilan yuborish
✅ Lokatsiya tugmasi bilan manzil
✅ Til tanlash (uz/ru/en)
✅ Yangi buyurtma (tur → galereya → xomashyo → razmer → savat → muddat → promo → yakun)
✅ Promokod qo'llash
✅ Admin ga avto-xabar (to'lov so'rovi)
✅ To'lov so'rovi cooldown (5 daqiqada 1 marta)
✅ Buyurtmalarim ro'yxati
✅ Admin: /admin → buyurtmalar → status o'zgartirish → mijoz avto-xabari
✅ Admin: ism bo'yicha qidirish
✅ Admin: broadcast (bloklaganlar ro'yxati bilan)
✅ Admin: statistika (umumiy + funnel + dropoff)
✅ Admin: Excel eksport (7 varaq)
✅ Admin: adminlar boshqaruvi (rol o'zgartirish)
✅ Admin: promo yaratish
✅ Admin: sharhlar ko'rish
✅ Admin: sozlamalar toggle
✅ Scheduler: drop-off eslatma (faqat 1 marta)
✅ Scheduler: tark_etdi belgilash
✅ Scheduler: kunlik/haftalik hisobot
✅ Mijoz baholash (1-5 yulduz + izoh)
