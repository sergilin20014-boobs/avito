#!/bin/bash
# deploy.sh — быстрый деплой на чистый Ubuntu 22.04
# Запуск: sudo bash deploy.sh
set -e

echo "=============================="
echo " Avito Bot — Деплой на Ubuntu"
echo "=============================="

# 1. Обновление системы и Python
echo "[1/7] Обновление пакетов..."
apt-get update -qq && apt-get install -y python3.11 python3.11-venv python3-pip git -qq

# 2. Создание директории проекта
echo "[2/7] Подготовка директории..."
mkdir -p /opt/avito_bot
cd /opt/avito_bot

# 3. Виртуальное окружение
echo "[3/7] Создание venv..."
python3.11 -m venv venv
source venv/bin/activate

# 4. Установка зависимостей
echo "[4/7] Установка зависимостей..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 5. .env
if [ ! -f .env ]; then
    echo "[5/7] Создание .env из шаблона..."
    cp .env.example .env
    echo ""
    echo "⚠️  ЗАПОЛНИТЕ /opt/avito_bot/.env перед запуском!"
    echo "     nano /opt/avito_bot/.env"
else
    echo "[5/7] .env уже существует, пропускаем."
fi

# 6. Systemd-сервис
echo "[6/7] Создание systemd-сервиса..."
cat > /etc/systemd/system/avito_bot.service << 'SERVICE'
[Unit]
Description=Avito Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/avito_bot
EnvironmentFile=/opt/avito_bot/.env
ExecStart=/opt/avito_bot/venv/bin/python bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable avito_bot

# 7. Запуск
echo "[7/7] Запуск бота..."
systemctl start avito_bot

echo ""
echo "=============================="
echo "✅ Бот запущен!"
echo "Статус:  systemctl status avito_bot"
echo "Логи:    journalctl -u avito_bot -f"
echo "         tail -f /opt/avito_bot/logs/bot.log"
echo "=============================="
