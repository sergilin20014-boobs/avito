"""
middlewares/update_logger.py — лог входящих Telegram-апдейтов.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

logger = logging.getLogger(__name__)

SLOW_UPDATE_MS = 500


def _user_label(user) -> str:
    if not user:
        return "user=?"
    name = f"@{user.username}" if user.username else (user.full_name or "?")
    return f"user={user.id} {name}"


def _describe_update(update: Update) -> str:
    if update.message:
        msg: Message = update.message
        label = _user_label(msg.from_user)
        if msg.text:
            text = msg.text
            if len(text) > 100:
                text = text[:100] + "…"
            return f"message {label} | {text!r}"
        if msg.contact:
            return f"contact {label} | phone={msg.contact.phone_number}"
        if msg.document:
            fname = msg.document.file_name or "file"
            return f"document {label} | {fname}"
        if msg.photo:
            return f"photo {label}"
        return f"message {label} | type={msg.content_type}"

    if update.callback_query:
        cb: CallbackQuery = update.callback_query
        label = _user_label(cb.from_user)
        return f"callback {label} | {cb.data!r}"

    event_type = update.event_type or "unknown"
    return f"update_id={update.update_id} type={event_type}"


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        desc = _describe_update(event)
        logger.info(desc)

        start = time.perf_counter()
        result = await handler(event, data)

        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= SLOW_UPDATE_MS:
            logger.warning("Медленный update (%.0f ms): %s", elapsed_ms, desc)
        else:
            logger.debug("Обработан за %.0f ms: %s", elapsed_ms, desc)

        return result
