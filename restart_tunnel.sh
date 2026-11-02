#!/bin/bash

# Har doim backend papkasiga o'tish
cd "$(dirname "$0")"
BACKEND_DIR="$(pwd)"
PROJECT_ROOT="$(dirname "$BACKEND_DIR")"

# Python interpreterini aniqlash (.venv, venv, tizim python)
PYTHON_BIN=""
CANDIDATES=(
    "$BACKEND_DIR/.venv/bin/python"
    "$PROJECT_ROOT/.venv/bin/python"
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "$VIRTUAL_ENV/bin/python"
    "python3"
    "python"
)

for py in "${CANDIDATES[@]}"; do
    if [ -n "$py" ] && ([ -x "$py" ] || command -v "$py" &>/dev/null); then
        if $py -c "import django" &>/dev/null; then
            PYTHON_BIN="$py"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Xatolik: Django o'rnatilgan Python topilmadi!"
    exit 1
fi

echo "🔹 Python topildi: $PYTHON_BIN"

# .env faylidagi kalit qiymatini yangilash funksiyasi (macOS va Linux uchun mos)
update_env_var() {
    local key="$1"
    local value="$2"
    local file="$3"

    if [ ! -f "$file" ]; then
        return 1
    fi

    # Fayl oxiri bo'sh qator bilan tugaganligini tekshirish (yangi qatorga yozish uchun)
    if [ -s "$file" ] && [ "$(tail -c 1 "$file")" != $'\n' ]; then
        echo "" >> "$file"
    fi

    if grep -q "^${key}=" "$file"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' -e "s|^${key}=.*|${key}=${value}|g" "$file"
        else
            sed -i -e "s|^${key}=.*|${key}=${value}|g" "$file"
        fi
    else
        echo "${key}=${value}" >> "$file"
    fi
    return 0
}

# 8000-portda Django backend ishlab turganini tekshirish
if ! lsof -i :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Ogohlantirish: Port 8000 da Django server topilmadi!"
    echo "    Boshqa terminalda 'python manage.py runserver 8000' ni ishga tushirganingizga ishonch hosil qiling."
fi

echo "🔄 Eski tunnellar to'xtatilmoqda..."
pkill -f "localhost.run" 2>/dev/null
pkill cloudflared 2>/dev/null
sleep 2

# SSH kaliti mavjud bo'lsa ishlatish
SSH_KEY_OPT=""
if [ -f "$HOME/.ssh/lhr_key" ]; then
    SSH_KEY_OPT="-i $HOME/.ssh/lhr_key"
fi

LOG_FILE="$BACKEND_DIR/tunnel_lhr.log"
> "$LOG_FILE"

echo "🚀 Yangi localhost.run tunnel ishga tushirilmoqda (port 8000)..."
ssh $SSH_KEY_OPT -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run > "$LOG_FILE" 2>&1 &
TUNNEL_PID=$!

echo "⏳ Kutib turing, tunnel URL olinmoqda..."

# 20 soniyagacha yangi URL ni kutish
NEW_URL=""
for i in {1..20}; do
    NEW_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.lhr\.life' "$LOG_FILE" 2>/dev/null | head -n 1)
    if [ -n "$NEW_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$NEW_URL" ]; then
    echo "❌ Xatolik: Yangi URL topilmadi. $LOG_FILE faylini tekshiring."
    [ -f "$LOG_FILE" ] && tail -n 20 "$LOG_FILE"
    exit 1
fi

echo "✅ Yangi Tunnel URL: $NEW_URL"

# Backend .env faylini yangilash
echo "📝 Backend .env fayli yangilanmoqda..."
if [ -f ".env" ]; then
    update_env_var "SITE_URL" "$NEW_URL" ".env"
    update_env_var "TELEGRAM_BOT_WEBHOOK_DOMAIN" "$NEW_URL" ".env"
    echo "   Backend .env yangilandi: SITE_URL=$NEW_URL"
else
    echo "⚠️  Ogohlantirish: Backend .env fayli topilmadi."
fi

# Telegram DNS yangilanishi va Webhook sozlash (retry loop bilan)
echo "🔗 Telegram Webhook yangilanmoqda..."
SUCCESS=0
for i in {1..5}; do
    echo "   Webhook o'rnatilmoqda (urinish $i/5)..."
    OUTPUT=$($PYTHON_BIN manage.py set_webhook --url="$NEW_URL" 2>&1)
    echo "   $OUTPUT"
    if [[ "$OUTPUT" == *"Telegram webhook o'rnatildi"* || "$OUTPUT" == *"muvaffaqiyatli"* ]]; then
        SUCCESS=1
        break
    fi
    echo "   Telegram serveri hozircha ulanolmadi, 3 soniya kutamiz..."
    sleep 3
done

if [ $SUCCESS -eq 0 ]; then
    echo "⚠️  Webhook o'rnatishda xatolik yuz berdi. Iltimos yuqoridagi xatolik xabarini tekshiring."
fi

# Eski WebApp menyu tugmasini tozalash (Buyruqlar menyusiga qaytarish)
echo "🧹 Telegram menyu tugmasi tozalanmoqda..."
$PYTHON_BIN manage.py shell -c "
import requests
from telegram_bot.models import TelegramBotConfig
token = TelegramBotConfig.load().bot_token
if token:
    requests.post(f'https://api.telegram.org/bot{token}/setChatMenuButton', json={'menu_button': {'type': 'default'}}, timeout=5)
" 2>/dev/null

# Django server settings faylini yangilash (auto-reload uchun)
if [ -f "config/settings.py" ]; then
    touch config/settings.py
fi

# Webhook holatini tekshirish
echo "🔍 Webhook holati tekshirilmoqda..."
$PYTHON_BIN manage.py shell -c "
import requests, json
from telegram_bot.models import TelegramBotConfig
token = TelegramBotConfig.load().bot_token
if token:
    res = requests.get(f'https://api.telegram.org/bot{token}/getWebhookInfo', timeout=5).json()
    if res.get('ok'):
        info = res['result']
        print(f'   URL: {info.get(\"url\")}')
        print(f'   Pending updates: {info.get(\"pending_update_count\", 0)}')
        if info.get('last_error_message'):
            print(f'   Oxirgi xatolik: {info.get(\"last_error_message\")}')
        else:
            print('   Telegram webhook to\'liq faol holatda!')
" 2>/dev/null

echo ""
echo "🎉 Barcha ishlar muvaffaqiyatli yakunlandi!"
echo "👉 Telegram bot endi yangi tunnel orqali so'rovlarni qabul qiladi."
echo "👉 Tunnel orqa fonda (PID: $TUNNEL_PID) ishlab turibdi."
