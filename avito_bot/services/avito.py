"""
services/avito.py — обработка Webhook-уведомлений от нескольких аккаунтов Авито.

Авито шлёт POST-запросы на ваш сервер при новых сообщениях в чате.
Каждый магазин настраивается отдельно в Авито Партнёрском API:
  POST https://api.avito.ru/webhook/v2/chatMessage

В заголовке X-Avito-Signature (или query-param `token`) передаётся секрет,
по которому мы определяем, от какого магазина пришёл запрос.

Этот модуль реализует полную логику Fork Point воронки Авито → Telegram:
  - Приветственный хук при первом сообщении
  - Парсинг номера телефона (Вариант А) → диплинк в Telegram
  - Fallback (Вариант Б) → ручной режим + алерт менеджеру
"""
import re
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any

from aiogram import Bot
from config import AVITO_ACCOUNTS, avito_chat_url, config, BOT_TOKEN

logger = logging.getLogger(__name__)

# Регулярное выражение для поиска российских номеров телефона
_PHONE_RE = re.compile(
    r'(?:\+7|8)[\s\(-]*\d{3}[\s\)-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}|\b9\d{9}\b'
)


# ─── Идентификация магазина ────────────────────────────────────────────────────

def identify_shop(secret_token: str) -> Optional[Dict[str, Any]]:
    """
    Определяет магазин по секретному токену из Webhook-запроса.
    Возвращает dict с данными магазина или None, если токен неизвестен.
    """
    return AVITO_ACCOUNTS.get(secret_token)


# ─── Нормализация телефона ─────────────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """
    Нормализует найденный номер до формата 7XXXXXXXXXX.
    Примеры: '+7 (999) 123-45-67' → '79991234567'
             '89991234567'        → '79991234567'
             '9991234567'         → '79991234567'
    """
    digits = re.sub(r'\D', '', raw)
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    return digits


# ─── Отправка сообщений в Авито ───────────────────────────────────────────────

async def send_avito_message(
    account_token: str,
    chat_id: str,
    message_text: str,
) -> bool:
    """
    Отправляет сообщение клиенту в чат Авито от лица магазина.
    account_token — OAuth2-токен конкретного аккаунта Авито.
    """
    url = f"https://api.avito.ru/messenger/v1/accounts/me/chats/{chat_id}/messages"
    headers = {
        "Authorization": f"Bearer {account_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {"text": message_text},
        "type": "text",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                logger.info("Сообщение отправлено в чат %s", chat_id)
                return True
            else:
                body = await resp.text()
                logger.error(
                    "Ошибка отправки в чат %s: HTTP %s — %s",
                    chat_id, resp.status, body[:300],
                )
                return False


# ─── Парсинг входящего Webhook ─────────────────────────────────────────────────

def parse_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Разбирает входящий Webhook от Авито v2 (chatMessage).
    Возвращает нормализованный dict.
    """
    value = payload.get("value", {})
    chat_id = value.get("chat_id", "")
    author = value.get("author", {})
    content = value.get("content", {})

    return {
        "chat_id": chat_id,
        "avito_chat_url": avito_chat_url(chat_id),
        "user_id": author.get("id", ""),
        "user_name": author.get("name", "Клиент Авито"),
        "message_text": content.get("text", ""),
        "timestamp": value.get("created", ""),
    }


# ─── Главная логика Fork Point ─────────────────────────────────────────────────

async def handle_avito_logic(
    bot: Bot,
    payload: Dict[str, Any],
    shop_name: str,
    account_token: str,
) -> None:
    """
    Полная логика воронки Авито → Telegram (Fork Point).

    Состояния avito_step:
      'welcome'           — новый чат, ещё не отвечали
      'waiting_for_phone' — отправили запрос телефона, ждём
      'completed'         — телефон получен, диплинк отправлен

    chat_status:
      'auto'        — бот управляет диалогом
      'manual_mode' — бот молчит, работает менеджер вручную
    """
    # Импорт здесь во избежание циклических зависимостей
    from database import get_user_by_avito_chat, upsert_avito_user

    event = parse_webhook_payload(payload)
    chat_id: str = event["chat_id"]
    message_text: str = event.get("message_text", "").strip()

    if not chat_id:
        logger.warning("Webhook без chat_id, игнорируем")
        return

    logger.info("Чат %s | %s | %r", chat_id, shop_name, message_text)

    # Достаём текущее состояние воронки из БД
    user = await get_user_by_avito_chat(chat_id)

    # ── Режим manual_mode: бот полностью молчит ──────────────────────────────
    if user and user.get("chat_status") == "manual_mode":
        logger.info("Чат %s в ручном режиме, пропускаем", chat_id)
        return

    # ── Новый чат (welcome) ───────────────────────────────────────────────────
    if not user or user.get("avito_step") in (None, "welcome"):
        # Создаём/обновляем запись
        await upsert_avito_user(
            avito_chat_id=chat_id,
            avito_shop=shop_name,
            avito_step="waiting_for_phone",
            chat_status="auto",
        )
        # ── Вариант В: безопасный скрипт без упоминания Telegram/ВА/ТГ ─────────
        # Авито блокирует аккаунты за призывы переходить в другие мессенджеры.
        await send_avito_message(
            account_token,
            chat_id,
            "Отлично! Для оформления заказа, проверки СТС и расчёта доставки "
            "напишите, пожалуйста, ваш номер телефона. "
            "Наш менеджер в течение 2–5 минут проверит данные и свяжется с вами "
            "для согласования макета.",
        )
        logger.info("Чат %s: отправлен приветственный хук", chat_id)
        return

    # ── Ожидаем телефон ───────────────────────────────────────────────────────
    if user.get("avito_step") == "waiting_for_phone":
        phone_match = _PHONE_RE.search(message_text)

        # ── ВАРИАНТ А: нашли телефон ──────────────────────────────────────────
        if phone_match:
            raw_phone = phone_match.group(0)
            normalized = normalize_phone(raw_phone)

            # Сохраняем номер, помечаем шаг как completed
            await upsert_avito_user(
                avito_chat_id=chat_id,
                phone=normalized,
                avito_step="completed",
                chat_status="auto",
            )

            # Формируем диплинк-ссылку в Telegram
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            deeplink = f"https://t.me/{bot_username}?start=avito_{chat_id}"

            # Вариант В: на Авито НЕ упоминаем Telegram/ВА — только нейтральный ответ
            await send_avito_message(
                account_token,
                chat_id,
                "Спасибо! Номер принят ✅\n\n"
                "Наш менеджер свяжется с вами в течение 2–5 минут "
                "для согласования макета и расчёта доставки.",
            )
            logger.info(
                "Чат %s: телефон %s получен, deeplink=%s",
                chat_id, normalized, deeplink,
            )

            # Алерт менеджеру: сюда помещаем диплинк (он только в TG, не на Авито)
            if config.admin_chat_id:
                try:
                    await bot.send_message(
                        config.admin_chat_id,
                        f"🎯 <b>Лид перехвачен с Авито!</b>\n\n"
                        f"🏪 Магазин: {shop_name}\n"
                        f"📞 Телефон: <code>{normalized}</code>\n"
                        f"💬 <a href='{avito_chat_url(chat_id)}'>Открыть чат Авито</a>\n\n"
                        f"⚠️ Напишите клиенту в Telegram/WhatsApp по номеру {normalized}\n"
                        f"🔗 Или отправьте диплинк вручную: {deeplink}",
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                except Exception as e:
                    logger.error("Не удалось отправить алерт менеджеру: %s", e)

        # ── ВАРИАНТ Б: телефона нет — ручной режим ────────────────────────────
        else:
            await upsert_avito_user(
                avito_chat_id=chat_id,
                chat_status="manual_mode",
            )
            await send_avito_message(
                account_token,
                chat_id,
                "Передаю диалог менеджеру, он ответит вам в ближайшее время...",
            )
            logger.info("Чат %s: телефон не распознан → manual_mode", chat_id)

            # Экстренный пуш менеджеру — он должен ответить вручную
            if config.admin_chat_id:
                try:
                    await bot.send_message(
                        config.admin_chat_id,
                        f"⚠️ <b>Клиент на Авито оставил сообщение — нужна ручная обработка!</b>\n\n"
                        f"🏪 Магазин: {shop_name}\n"
                        f"💬 <a href='{avito_chat_url(chat_id)}'>Открыть чат Авито →</a>\n\n"
                        f"Сообщение: «{message_text[:300]}»\n\n"
                        f"Срочно напишите клиенту в Telegram/WhatsApp!",
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                except Exception as e:
                    logger.error("Не удалось отправить экстренный пуш менеджеру: %s", e)

        return

    # ── Шаг 'completed': диалог уже переведён в Telegram ─────────────────────
    if user.get("avito_step") == "completed":
        await send_avito_message(
            account_token,
            chat_id,
            "Ваша заявка уже в работе! ✅ "
            "Менеджер свяжется с вами для согласования макета.",
        )
        logger.info("Чат %s: повторное сообщение после completed", chat_id)
