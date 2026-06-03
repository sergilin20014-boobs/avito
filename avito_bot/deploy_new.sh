# Запуск: sudo bash deploy.sh
set -e

echo "=============================="
echo " Avito Bot — Деплой на AlmaLinux"
echo "=============================="

# 1. Обновление системы и Python 3.11
echo "[1/7] Установка Python 3.11..."
dnf install -y epel-release 
dnf install -y python311 git 

# 2. Создание директории проекта
echo "[2/7] Подготовка директории..."
mkdir -p /opt/avito_bot
cd /opt/avito_bot

# 3. Виртуальное окружение
echo "[3/7] Создание venv на базе Python 3.11..."
# Сносим старый кривой venv, если он остался от прошлых тестов
rm -rf venv 
# Явно вызываем бинарник 3.11 для создания окружения
python3.11 -m venv venv
source venv/bin/activate

# Проверка "на всякий случай" внутри активированного venv
echo "Смотри сюда! Версия Python в окружении теперь:"
python --version

# 4. Установка зависимостей
echo "[4/7] Установка зависимостей..."
pip install --upgrade pip -q
pip install -r /opt/avito_bot/requirements.txt -q

# 5. .env
if [ ! -f .env ]; then
	    echo "[5/7] Создание .env из шаблона..."
	        if [ -f .env.example ]; then
			        cp .env.example .env
				    else
					            touch .env
						        fi
							    echo ""
							        echo "⚠️  ЗАПОЛНИТЕ /opt/avito_bot/.env перед запуском!"
								    echo "    nano /opt/avito_bot/.env"
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
# Здесь venv/bin/python уже гарантированно будет версией 3.11
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
systemctl start avito_bot || echo "ℹ️ Сервис создан, но не запустился (возможно, не заполнен .env)"

echo ""
echo "=============================="
echo "✅ Бот развернут!"
echo "Статус:  systemctl status avito_bot"
echo "Логи:    journalctl -u avito_bot -f"
echo "=============================="
