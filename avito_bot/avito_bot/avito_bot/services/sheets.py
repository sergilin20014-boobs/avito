"""
services/sheets.py — запись заказов в Google Таблицу через gspread (sync в executor).
Используем run_in_executor, т.к. gspread — синхронная библиотека.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_ID, GOOGLE_WORKSHEET_NAME

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "ID заказа", "Дата", "Юзернейм", "Тип (Опт/Розница)",
    "Источник", "Авито-магазин", "Категория", "Подкатегория",
    "Текст плашки", "Ссылка на файл (Telegram)", "Тип доставки",
    "ФИО (СДЭК)", "Телефон (СДЭК)", "Город (СДЭК)", "Адрес ПВЗ",
    "Трек-номер СДЭК", "Документ (file_id)", "Статус",
]


def _get_worksheet():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = spreadsheet.worksheet(GOOGLE_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=GOOGLE_WORKSHEET_NAME, rows=1000, cols=20)
        ws.append_row(HEADERS)
    return ws


def _sync_append_order(order: Dict[str, Any]) -> None:
    ws = _get_worksheet()
    row = [
        order.get("id", ""),
        order.get("created_at", datetime.now().isoformat()),
        order.get("username", ""),
        order.get("client_type", ""),
        order.get("source", "telegram"),
        order.get("avito_shop", ""),
        order.get("category", ""),
        order.get("subcategory", ""),
        order.get("plate_text", ""),
        order.get("file_id", ""),
        order.get("delivery_type", ""),
        order.get("cdek_fio", ""),
        order.get("cdek_phone", order.get("phone", "")),  # <-- ИСПРАВЛЕНО: ищет оба ключа, чтобы точно записать номер!
        order.get("cdek_city", ""),
        order.get("cdek_pvz", ""),
        order.get("cdek_track", ""),
        order.get("doc_file_id", ""),
        order.get("status", "new"),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Заказ #%s записан в Google Sheets", order.get("id"))

async def append_order_to_sheet(order: Dict[str, Any]) -> None:
    """Асинхронная обёртка для синхронного gspread."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _sync_append_order, order)
    except Exception as e:
        logger.error("Ошибка записи в Google Sheets: %s", e)
