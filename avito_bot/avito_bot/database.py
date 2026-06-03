"""
database.py — асинхронная работа с SQLite через aiosqlite.
Таблицы: orders (заказы), users (клиенты).

v2: добавлены поля воронки Авито:
  phone        TEXT          — номер телефона клиента
  avito_step   TEXT          — текущий шаг на Авито ('welcome' | 'waiting_for_phone' | 'completed')
  chat_status  TEXT          — режим чата ('auto' | 'manual_mode')
"""
import aiosqlite
from datetime import datetime
from typing import Optional, Dict, Any
from config import config

DB = config.db_path


async def init_db() -> None:
    """Создаёт таблицы при первом запуске. Добавляет новые колонки если таблица уже существует."""
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                client_type   TEXT,               -- 'opt' | 'retail'
                source        TEXT DEFAULT 'telegram',  -- 'telegram' | 'avito'
                avito_shop    TEXT,               -- название авито-магазина
                avito_chat_id TEXT,               -- ID чата Авито
                phone         TEXT,               -- номер телефона (из воронки Авито)
                avito_step    TEXT DEFAULT 'welcome',   -- шаг воронки Авито
                chat_status   TEXT DEFAULT 'auto',      -- 'auto' | 'manual_mode'
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        # Миграция: добавляем новые колонки, если таблица уже существовала без них
        for col, definition in [
            ("phone",       "TEXT"),
            ("avito_step",  "TEXT DEFAULT 'welcome'"),
            ("chat_status", "TEXT DEFAULT 'auto'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            except Exception:
                pass  # колонка уже есть

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                username        TEXT,
                client_type     TEXT,
                source          TEXT DEFAULT 'telegram',
                avito_shop      TEXT,
                avito_chat_id   TEXT,
                category        TEXT,
                subcategory     TEXT,
                plate_text      TEXT,
                file_id         TEXT,       -- Telegram file_id загруженного файла
                delivery_type   TEXT,       -- 'pickup' | 'cdek'
                cdek_fio        TEXT,
                cdek_phone      TEXT,
                cdek_city       TEXT,
                cdek_pvz        TEXT,
                cdek_track      TEXT,       -- трек-номер СДЭК
                doc_file_id     TEXT,       -- file_id фото СТС/ПТС
                status          TEXT DEFAULT 'new',
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


async def upsert_user(
    user_id: int,
    username: Optional[str],
    client_type: Optional[str] = None,
    source: str = "telegram",
    avito_shop: Optional[str] = None,
    avito_chat_id: Optional[str] = None,
    phone: Optional[str] = None,
    avito_step: Optional[str] = None,
    chat_status: Optional[str] = None,
) -> None:
    """
    Создаёт или обновляет запись пользователя.
    Поля, переданные как None, не перезаписывают существующие значения (COALESCE).
    """
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO users (
                user_id, username, client_type, source,
                avito_shop, avito_chat_id, phone, avito_step, chat_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username      = excluded.username,
                client_type   = COALESCE(excluded.client_type,   client_type),
                source        = excluded.source,
                avito_shop    = COALESCE(excluded.avito_shop,    avito_shop),
                avito_chat_id = COALESCE(excluded.avito_chat_id, avito_chat_id),
                phone         = COALESCE(excluded.phone,         phone),
                avito_step    = COALESCE(excluded.avito_step,    avito_step),
                chat_status   = COALESCE(excluded.chat_status,   chat_status)
        """, (
            user_id, username, client_type, source,
            avito_shop, avito_chat_id, phone, avito_step, chat_status,
        ))
        await db.commit()


async def upsert_avito_user(
    avito_chat_id: str,
    avito_shop: Optional[str] = None,
    phone: Optional[str] = None,
    avito_step: Optional[str] = None,
    chat_status: Optional[str] = None,
) -> None:
    """
    Создаёт/обновляет запись пользователя, пришедшего с Авито,
    используя avito_chat_id как суррогатный ключ (user_id = хэш chat_id).
    Отдельная функция, чтобы не путать с Telegram user_id.
    """
    # Суррогатный user_id для Авито-пользователей: отрицательное число на базе hash
    surrogate_id = -(abs(hash(avito_chat_id)) % (10 ** 15))
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO users (
                user_id, username, source,
                avito_chat_id, avito_shop, phone, avito_step, chat_status
            )
            VALUES (?, ?, 'avito', ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                avito_chat_id = COALESCE(excluded.avito_chat_id, avito_chat_id),
                avito_shop    = COALESCE(excluded.avito_shop,    avito_shop),
                phone         = COALESCE(excluded.phone,         phone),
                avito_step    = COALESCE(excluded.avito_step,    avito_step),
                chat_status   = COALESCE(excluded.chat_status,   chat_status)
        """, (
            surrogate_id, None,
            avito_chat_id, avito_shop, phone, avito_step, chat_status,
        ))
        await db.commit()


async def get_user_by_avito_chat(avito_chat_id: str) -> Optional[Dict[str, Any]]:
    """Возвращает запись пользователя по ID чата Авито (для логики воронки)."""
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE avito_chat_id = ? LIMIT 1",
            (avito_chat_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """
    Ищет Авито-пользователя по нормализованному номеру телефона.
    Используется при авторизации через Telegram, чтобы связать аккаунты.
    """
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE phone = ? AND source = 'avito' LIMIT 1",
            (phone,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_order(data: Dict[str, Any]) -> int:
    """Создаёт заказ и возвращает его ID."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    values = list(data.values())
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            f"INSERT INTO orders ({columns}) VALUES ({placeholders})",
            values,
        )
        await db.commit()
        return cursor.lastrowid


async def update_order(order_id: int, **kwargs) -> None:
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [order_id]
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE orders SET {sets} WHERE id = ?", values)
        await db.commit()


async def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
