"""
config.py — центральный конфиг проекта.
Все секреты читаются из .env (или переменных окружения).
"""
import os
from dataclasses import dataclass, field
from typing import Dict
from dotenv import load_dotenv

load_dotenv()


# ─── Telegram ────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))   # ID приватного чата/канала менеджера

# ─── Google Sheets ────────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")      # ID таблицы из URL
GOOGLE_WORKSHEET_NAME: str = os.getenv("GOOGLE_WORKSHEET_NAME", "Заказы")

# ─── СДЭК API ────────────────────────────────────────────────────────────────
CDEK_API_URL: str = "https://api.edu.cdek.ru/v2"   # sandbox; prod: api.cdek.ru
CDEK_CLIENT_ID: str = os.getenv("CDEK_CLIENT_ID", "EMscd6r9JnFiQ3bLoyjJY6eM78JV9wBO")
CDEK_CLIENT_SECRET: str = os.getenv("CDEK_CLIENT_SECRET", "PjLZkKBHEiLK3YsjtNrt7ZQLfu3a5op5")

# ─── SQLite ───────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "avito_bot.db")

# ─── Логирование ──────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")          # DEBUG | INFO | WARNING | ERROR
LOG_DIR: str = os.getenv("LOG_DIR", "logs")
LOG_FILE: str = os.getenv("LOG_FILE", "bot.log")
LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ─── Avito мультиаккаунт ─────────────────────────────────────────────────────
# Структура: { webhook_secret_token: { "name": "Название магазина", "account_id": "..." } }
# При обработке Webhook Авито передаёт X-Avito-Signature или аналог — по нему определяем магазин.
AVITO_ACCOUNTS: Dict[str, dict] = {
    os.getenv("AVITO_SECRET_SHOP1", "secret_shop1"): {
        "name": "Авито Магазин №1 — Номера",
        "account_id": os.getenv("AVITO_ACCOUNT_ID_SHOP1", "111111111"),
        "token": os.getenv("AVITO_TOKEN_SHOP1", ""),
    },
    os.getenv("AVITO_SECRET_SHOP2", "secret_shop2"): {
        "name": "Авито Магазин №2 — Рамки",
        "account_id": os.getenv("AVITO_ACCOUNT_ID_SHOP2", "222222222"),
        "token": os.getenv("AVITO_TOKEN_SHOP2", ""),
    },
}

# Ссылка на чат Авито (подставляем chat_id из webhook-данных)
def avito_chat_url(chat_id: str) -> str:
    return f"https://www.avito.ru/profile/messenger/channel/{chat_id}"


@dataclass
class Config:
    bot_token: str = BOT_TOKEN
    admin_chat_id: int = ADMIN_CHAT_ID
    db_path: str = DB_PATH
    google_credentials_file: str = GOOGLE_CREDENTIALS_FILE
    google_sheet_id: str = GOOGLE_SHEET_ID
    google_worksheet_name: str = GOOGLE_WORKSHEET_NAME
    avito_accounts: Dict[str, dict] = field(default_factory=lambda: AVITO_ACCOUNTS)


config = Config()
