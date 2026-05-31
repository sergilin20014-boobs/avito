"""
handlers/admin.py — всё для административных уведомлений:
  - Карточка нового заказа в ADMIN_CHAT_ID
  - Алерт при «Остаться на Авито»
  - Callback «Переслать на производство»
"""
import logging
from typing import Dict, Any, Optional
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config, avito_chat_url
from database import get_order

from catalog_data import NODES, get_product_label

logger = logging.getLogger(__name__)
router = Router()

CATEGORY_NAMES = {
    "numbers": "Номера",
    "frames": "Рамки",
}


def _product_name(order: Dict[str, Any]) -> str:
    if order.get("product_label"):
        return order["product_label"]
    sub = order.get("subcategory", "")
    if sub in NODES:
        return get_product_label(sub)
    return sub or "—"


def _format_order_card(order: Dict[str, Any]) -> str:
    client_type = "Опт" if order.get("client_type") == "opt" else "Розница"
    category = CATEGORY_NAMES.get(order.get("category", ""), order.get("category", ""))
    sub = _product_name(order)
    delivery = "СДЭК" if order.get("delivery_type") == "cdek" else "Самовывоз"
    source = order.get("avito_shop") or "Telegram"
    username = f"@{order.get('username')}" if order.get("username") else str(order.get("user_id"))

    cdek_block = ""
    if order.get("delivery_type") == "cdek":
        cdek_block = (
            f"\n📦 <b>СДЭК:</b>\n"
            f"  👤 {order.get('cdek_fio', '—')}\n"
            f"  📞 {order.get('cdek_phone', '—')}\n"
            f"  🏙️ {order.get('cdek_city', '—')}\n"
            f"  📍 {order.get('cdek_pvz', '—')}\n"
            f"  🔢 Трек: <code>{order.get('cdek_track', '—')}</code>"
        )

    avito_block = ""
    if order.get("avito_chat_id"):
        avito_block = f"\n🔗 <a href='{avito_chat_url(order['avito_chat_id'])}'>Чат Авито</a>"

    return (
        f"📥 <b>НОВЫЙ ГОТОВЫЙ ЗАКАЗ! #{order.get('id')}</b>\n\n"
        f"👤 Клиент: {username} ({client_type})\n"
        f"🏪 Источник: {source}"
        f"{avito_block}\n"
        f"🛠 Состав: {category} — {sub}\n"
        f"✍️ Текст/Плашка: {order.get('plate_text') or '—'}\n"
        f"🎨 Дизайн/Лого: {'✅ файл загружен' if order.get('file_id') else '—'}\n"
        f"📄 Документ СТС/ПТС: {'✅ загружен' if order.get('doc_file_id') else '—'}\n"
        f"🚚 Доставка: {delivery}"
        f"{cdek_block}"
    )


def _admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏭 Переслать на производство",
        callback_data=f"admin:forward:{order_id}",
    )
    return builder.as_markup()


async def notify_admin_new_order(bot: Bot, order: Dict[str, Any]) -> None:
    """Отправляет карточку нового заказа в чат менеджера."""
    if not config.admin_chat_id:
        logger.warning("ADMIN_CHAT_ID не задан, уведомление не отправлено.")
        return

    text = _format_order_card(order)
    order_id = order.get("id", 0)

    try:
        # Если есть загруженный файл дизайна — пересылаем его тоже
        if order.get("file_id"):
            await bot.send_photo(
                config.admin_chat_id,
                photo=order["file_id"],
                caption=f"🎨 Файл дизайна к заказу #{order_id}",
            )

        if order.get("doc_file_id"):
            await bot.send_photo(
                config.admin_chat_id,
                photo=order["doc_file_id"],
                caption=f"📄 СТС/ПТС к заказу #{order_id}",
            )

        await bot.send_message(
            config.admin_chat_id,
            text,
            parse_mode="HTML",
            reply_markup=_admin_order_kb(order_id),
            disable_web_page_preview=True,
        )
        logger.info("Уведомление о заказе #%s отправлено менеджеру", order_id)
    except Exception as e:
        logger.error("Не удалось уведомить менеджера о заказе #%s: %s", order_id, e)


async def notify_admin_avito_stay(
    bot: Bot,
    avito_chat_id: str,
    shop_name: str,
    username: Optional[str] = None,
) -> None:
    """
    Алерт когда клиент нажал «Остаться на Авито».
    Отправляет ссылку на чат Авито менеджеру.
    """
    if not config.admin_chat_id:
        return
    user_label = f"@{username}" if username else "клиент"
    chat_link = avito_chat_url(avito_chat_id)
    text = (
        f"⚠️ <b>Клиент остался на Авито</b>\n\n"
        f"👤 {user_label}\n"
        f"🏪 Магазин: {shop_name}\n"
        f"💬 <a href='{chat_link}'>Перейти в чат Авито</a>\n\n"
        "Необходимо продолжить общение вручную."
    )
    try:
        await bot.send_message(
            config.admin_chat_id,
            text,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except Exception as e:
        logger.error("Ошибка уведомления о клиенте Авито: %s", e)


# ─── Callback: переслать на производство ─────────────────────────────────────

def _production_card(order: Dict[str, Any]) -> str:
    """Форматирует карточку для мастера (производство)."""
    category = CATEGORY_NAMES.get(order.get("category", ""), order.get("category", ""))
    sub = _product_name(order)
    delivery = "СДЭК" if order.get("delivery_type") == "cdek" else "Самовывоз"
    return (
        f"🏭 <b>ПРОИЗВОДСТВЕННЫЙ ЗАКАЗ #{order.get('id')}</b>\n\n"
        f"📦 Изделие: {category} — {sub}\n"
        f"✍️ Текст/Плашка: {order.get('plate_text') or '—'}\n"
        f"🎨 Дизайн: {'✅ файл прикреплён выше' if order.get('file_id') else 'нет'}\n"
        f"🚚 Отправка: {delivery}\n"
        + (
            f"📦 Трек СДЭК: <code>{order.get('cdek_track')}</code>\n"
            f"📍 ПВЗ: {order.get('cdek_pvz', '—')}, {order.get('cdek_city', '—')}\n"
            if order.get("delivery_type") == "cdek" else ""
        )
        + f"\n📅 Создан: {order.get('created_at', '—')}"
    )


@router.callback_query(F.data.startswith("admin:forward:"))
async def forward_to_production(call: CallbackQuery, bot: Bot) -> None:
    order_id = int(call.data.split(":")[2])
    order = await get_order(order_id)

    if not order:
        await call.answer("Заказ не найден в БД.", show_alert=True)
        return

    prod_text = _production_card(order)

    if order.get("file_id"):
        await call.message.answer_photo(
            photo=order["file_id"],
            caption=f"🎨 Дизайн к заказу #{order_id}",
        )

    await call.message.answer(prod_text, parse_mode="HTML")
    await call.answer("✅ Переслано на производство!")
    logger.info("Заказ #%s переслан на производство", order_id)
