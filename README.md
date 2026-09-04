# To'yxona va Bar Booking API

O'zbekiston bozoriga moslashtirilgan to'yxonalar (smena bo'yicha) va barlarni
(soatlik) bron qilish hamda boshqarish uchun Django REST API.

## Texnologiyalar

- Python 3.11+
- Django 5.2 va Django REST Framework
- PostgreSQL (local development uchun SQLite fallback)
- SimpleJWT + Djoser orqali telefon raqamli autentifikatsiya
- Celery + Redis orqali bron va Telegram bildirishnomalari
- drf-spectacular orqali OpenAPI/Swagger
- WhiteNoise orqali production static fayllar

## Ishga tushirish

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
pip install -e .
python manage.py migrate
python manage.py seed_data                 # ixtiyoriy demo ma'lumotlar
python manage.py runserver
```

`USE_SQLITE=True` local uchun yetarli. Productionda `DEBUG=False`,
`USE_SQLITE=False`, PostgreSQL, kuchli `SECRET_KEY`, `ALLOWED_HOSTS`, CORS/CSRF
originlari va Redis qiymatlarini albatta sozlang. Deploymentdan oldin static
fayllarni yig'ing:

```bash
python manage.py collectstatic --noinput
```

Swagger: <http://127.0.0.1:8000/api/docs/>
Schema: <http://127.0.0.1:8000/api/schema/>
Health check: <http://127.0.0.1:8000/health/>

## Fon jarayonlari

Bron egasiga Telegram xabari faqat database transaction muvaffaqiyatli commit
bo'lgandan keyin Celery queue'ga yuboriladi. Worker va scheduler:

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Har soatda muddati o'tgan `HOLD` bronlar `CANCELLED` qilinadi. Telegram botni
admin API orqali yoki command orqali ulash mumkin:

```bash
python manage.py set_webhook --url https://example.com
# bekor qilish:
python manage.py set_webhook --delete
```

Telegram webhook URL to'liq ko'rsatilmasa, command uni
`/api/v1/bot/webhook/` bilan to'ldiradi. `TELEGRAM_WEBHOOK_SECRET` sozlansa,
webhook requestlarida Telegram secret header ham tekshiriladi.

## API yo'nalishlari

- `POST /api/v1/auth/users/` — client yoki venue owner ro'yxatdan o'tishi
- `POST /api/v1/auth/jwt/create/` — JWT olish
- `GET /api/v1/venues/halls/` va `/bars/` — public qidiruv va filterlar
- `GET /api/v1/bookings/calendar/hall/<id>/` — `year` va `month` bilan kalendar
- `GET /api/v1/bookings/calendar/bar/<id>/` — band soatlar
- `POST /api/v1/bookings/hall/` yoki `/bar/` — yangi `PENDING` bron
- `PATCH /api/v1/bookings/hall/<id>/status/` yoki `/bar/<id>/status/` — owner/admin status boshqaruvi
- `/api/v1/bot/webhook/` — Telegram webhook
- `/api/v1/bot/admin/bot-config/` — faqat platform admini uchun bot sozlamalari

Hall booking narxi paket va dekoratsiyadan, bar booking narxi esa vaqt oralig'i
va `price_per_hour` dan server tomonda hisoblanadi. Mijoz narxni yoki `user`
maydonini o'zgartira olmaydi. `HOLD`, `PENDING` va `CONFIRMED` bronlar
availability hisobida faol; `REJECTED` va `CANCELLED` bo'sh slot hisoblanadi.

## Sifat tekshiruvi

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Bron yaratish va status o'zgarishlarida venue qatori lock qilinadi, shuning uchun
bir vaqtdagi so'rovlar double-bookingga olib kelmaydi. Katta ro'yxatlar uchun
venue va booking availability/filter indexlari qo'shilgan.
