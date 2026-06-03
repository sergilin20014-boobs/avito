"""
middlewares/error_handler.py — глобальный ErrorHandler для aiogram 3.x.
При любом необработанном исключении:
  - клиент получает friendly-сообщение;
  - в ADMIN_CHAT_ID летит полный stack trace.
"""
import logging
import traceback
from aiogram import Bot
from aiogram.types import Update, ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from config import config

logger = logging.getLogger(__name__)


async def global_error_handler(event: ErrorEvent, bot: Bot) -> bool:
    """
    Регистрируется через dp.errors.register(global_error_handler).
    Возвращает True — aiogram не поднимает исключение дальше.
    """
    exc = event.exception
    update: Update = event.update

    # Логируем
    update_id = update.update_id
    logger.error("Необработанная ошибка (update_id=%s): %s", update_id, exc, exc_info=True)

    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    tb_short = tb_text[-3500:]  # Telegram лимит ~4096 символов

    # Уведомляем клиента
    chat_id: int | None = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat.id  # type: ignore[union-attr]

    if chat_id:
        try:
            await bot.send_message(
                chat_id,
                "⚠️ Что-то пошло не так. Менеджер уже уведомлён — мы разберёмся!",
            )
        except TelegramBadRequest:
            pass

    # Уведомляем администратора
    if config.admin_chat_id:
        try:
            await bot.send_message(
                config.admin_chat_id,
                f"🔴 <b>ОШИБКА БОТА</b>\n\n"
                f"Update: <code>{update.update_id}</code>\n\n"
                f"<pre>{tb_short}</pre>",
                parse_mode="HTML",
            )
        except Exception as admin_exc:
            logger.error("Не удалось отправить traceback админу: %s", admin_exc)

    return True
