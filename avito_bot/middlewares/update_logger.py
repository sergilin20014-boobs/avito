"""
middlewares/update_logger.py — информативный лог входящих Telegram-апдейтов.

Формат лога:
  [message]   user=123 @username | "текст сообщения"
  [callback]  user=123 @username | cat:s:n.st
  [contact]   user=123 @username | phone=79001234567
  [photo]     user=123 @username
  [document]  user=123 @username | file.pdf

Медленные апдейты (> SLOW_UPDATE_MS) логируются как WARNING с временем.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

logger = logging.getLogger(__name__)

# Порог «медленного» апдейта в миллисекундах
SLOW_UPDATE_MS = 500


def _user_label(user) -> str:
    """Читаемая метка пользователя: ID + @username или имя."""
    if not user:
        return "user=?"
    handle = f"@{user.username}" if user.username else (user.full_name or "—")
    return f"user={user.id} {handle}"


def _describe_update(update: Update) -> str:
    """Возвращает однострочное описание апдейта для лога."""
    if update.message:
        msg: Message = update.message
        label = _user_label(msg.from_user)

        if msg.text:
            # Обрезаем длинные сообщения
            text = msg.text if len(msg.text) <= 80 else msg.text[:80] + "…"
            # Команды выделяем отдельно для удобства фильтрации
            prefix = "command" if msg.text.startswith("/") else "message"
            return f"[{prefix}] {label} | {text!r}"

        if msg.contact:
            return f"[contact] {label} | phone={msg.contact.phone_number}"

        if msg.document:
            fname = msg.document.file_name or "file"
            return f"[document] {label} | {fname}"

        if msg.photo:
            return f"[photo] {label}"

        return f"[message] {label} | type={msg.content_type}"

    if update.callback_query:
        cb: CallbackQuery = update.callback_query
        label = _user_label(cb.from_user)
        return f"[callback] {label} | {cb.data!r}"

    event_type = update.event_type or "unknown"
    return f"[{event_type}] update_id={update.update_id}"


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        desc = _describe_update(event)

        # Логируем входящий апдейт
        logger.info("→ %s", desc)

        start = time.perf_counter()
        result = await handler(event, data)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Медленные апдейты — предупреждение с временем выполнения
        if elapsed_ms >= SLOW_UPDATE_MS:
            logger.warning("⚠ МЕДЛЕННО %.0f мс: %s", elapsed_ms, desc)
        else:
            logger.debug("✓ %.0f мс: %s", elapsed_ms, desc)

        return result