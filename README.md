# 🏛️ To'yxona & Bar Booking API

O'zbekiston bozoriga moslashtirilgan to'yxonalar (smenali tizim) va barlarni (soatlik ijaraga berish) bron qilish va boshqarish uchun mo'ljallangan backend platforma.

## 🚀 Loyiha haqida
Ushbu API mijozlarga o'ziga mos to'y zali yoki kuyov navkar barini topish, paket va dekoratsiya tanlash hamda real vaqt rejimida bo'sh sanalarni ko'rib bron yuborish imkonini beradi. 

Joy egalari uchun esa xonalar va smenalarni moslashuvchan boshqarish, sanalarni muzlatib turish (`HOLD` rejimi) va Telegram bot orqali yangi bronlar haqida tezkor xabar olish imkoniyati mavjud.

## 🛠 Texnologiyalar
* **Python 3.10+**
* **Django 5.0+** & **Django REST Framework (DRF)**
* **PostgreSQL** — Asosiy relatsion ma'lumotlar bazasi
* **Celery & Redis** — Asinxron fon vazifalari (HOLD muddatini nazorat qilish va Telegram botga xabar yuborish)
* **SimpleJWT / Djoser** — Token asosida avtentifikatsiya
* **OpenAPI / Swagger (drf-spectacular)** — API hujjatlashtirish

## 📁 Loyiha strukturasi
```text
config/             # Asosiy sozlamalar (settings, urls, celery)
├── users/          # Foydalanuvchi rollari va avtentifikatsiya
├── venues/         # Joylar (Hall, Bar, Shift, Package, Decoration)
├── bookings/       # Bronlash logikasi va kalendar algoritmlari
└── notifications/  # Telegram bot va SMS integratsiyalari

⚙️ O'rnatish yo'riqnomasi (Local setup)
Gid-repozitoriydan nusxa oling:

Bash
git clone [https://github.com/username/toyxona-booking-api.git](https://github.com/username/toyxona-booking-api.git)
cd toyxona-booking-api
Virtual muhit (venv) yarating va aktivlashtiring:

Bash
python3 -m venv venv
source venv/bin/activate  # Windows uchun: venv\Scripts\activate
Kutubxonalarni o'rnating:

Bash
pip install -r requirements.txt
Atrof-muhit o'zgaruvchilarini sozlang:
.env.example faylidan nusxa olib, yangi .env fayl yarating va PostgreSQL hamda Telegram Bot ma'lumotlarini kiritib chiqing:

Bash
cp .env.example .env
Ma'lumotlar bazasi migratsiyalarini bajaring:

Bash
python manage.py makemigrations
python manage.py migrate
Superuser (Admin) yarating:

Bash
python manage.py createsuperuser
Loyiha serverini ishga tushiring:

Bash
python manage.py runserver
API Hujjatlar (Swagger UI): http://127.0.0.1:8000/api/docs/

Django Admin Panel: http://127.0.0.1:8000/admin/

🔑 Asosiy xususiyatlar (Key Features)
Ikki xil model obyekti: WeddingHall (Smena va Paketlar bo'yicha) va Bar (Soatlik tarifikatsiya bo'yicha).

Double-booking proteksiyasi: Serializer darajasida sanalar kesishuvini va ustma-ust tushishni avtomat to'sadi.

HOLD mexanizmi: Restoran adminlari kelishuv jarayonida sanalarni 24-48 soatga muzlatib qo'ya oladi.

Yagona Kalendar API: Frontend taqvim chizishi uchun barcha band va bloklangan smenalarni bir so'rovda qaytaradigan optimallashtirilgan endpoint.


---

Loyiha uchun to'liq arxitektura va texnik hujjat tayyorlandi. Navbatda loyihani papkalarga ajratib, birinchi navbatda `venues` app modellarini yozishni boshlaymizmi yoki Telegram bot integratsiyasi mexanizmini ko'rib chiqamizmi?