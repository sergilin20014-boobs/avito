"""
handlers/manager.py — обработка кнопки «👤 Позвать менеджера».

Callback «mgr:call» может прийти из любого состояния FSM:
  - Пользователь получает подтверждение
  - Администратор получает алерт с контактными данными клиента
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "mgr:call")
async def call_manager(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Вызов менеджера из любой точки воронки."""
    user = call.from_user
    username_str = f"@{user.username}" if user.username else f"tg://user?id={user.id}"
    fsm_data = await state.get_data()

    # Пользователю — мгновенное подтверждение
    await call.answer(
        "Менеджер вызван, он свяжется с вами в ближайшее время!",
        show_alert=True,
    )
    await call.message.answer(
        "👤 <b>Менеджер вызван!</b>\n\nМы свяжемся с вами в ближайшее время.",
        parse_mode="HTML",
    )

    # Менеджеру — алерт с контекстом
    if config.admin_chat_id:
        category = fsm_data.get("category", "—")
        subcategory = fsm_data.get("subcategory", "—")
        avito_chat_id = fsm_data.get("avito_chat_id", "")

        avito_link = ""
        if avito_chat_id:
            from config import avito_chat_url
            avito_link = f"\n💬 <a href='{avito_chat_url(avito_chat_id)}'>Чат Авито</a>"

        try:
            await bot.send_message(
                config.admin_chat_id,
                f"🔔 <b>Клиент вызвал менеджера!</b>\n\n"
                f"👤 {username_str} (ID: <code>{user.id}</code>)\n"
                f"🏷️ Интересует: {category} → {subcategory}"
                f"{avito_link}",
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
        except Exception as e:
            logger.error("Не удалось отправить алерт менеджеру: %s", e)

    logger.info("Пользователь %s вызвал менеджера", user.id)
