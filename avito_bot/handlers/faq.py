"""
handlers/faq.py — блок FAQ на основе реальных клиентских болей.

Кнопка «❓ FAQ» в главном меню → этот роутер.
Каждый ответ — отдельный callback, возврат через «◀️ В главное меню».
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from states import FAQ, MainMenu
from keyboards import kb_faq, kb_main_menu

router = Router()

# ─── Тексты ответов ───────────────────────────────────────────────────────────

FAQ_TEXTS = {
    "law": (
        "⚖️ <b>Законность и ГОСТ</b>\n\n"
        "Наши стандартные и жирные номера полностью соответствуют ГОСТ. "
        "Проблем с ГАИ не будет.\n\n"
        "В производстве используются <b>немецкие износостойкие краски</b> и "
        "<b>бесплатная антикоррозийная обработка</b> — в отличие от китайских "
        "аналогов у конкурентов.\n\n"
        "🛡 <b>Гарантия на лакированные номера — 3 года.</b>"
    ),
    "pickup": (
        "🏭 <b>Изготовление и самовывоз</b>\n\n"
        "При самовывозе из офиса в Москве номера изготавливаются при вас "
        "<b>всего за 5 минут!</b>\n\n"
        "📍 <b>Адрес:</b> м. Менделеевская / Новослободская,\n"
        "ул. Новослободская 31с2\n"
        "⏰ Ежедневно с 10:00 до 22:00\n\n"
        "🚗 <b>Для въезда на авто:</b> заезжайте под белый шлагбаум около Novotel, "
        "скажите сторожу, что вы за номерами."
    ),
    "delivery": (
        "🚚 <b>Доставка</b>\n\n"
        "📍 <b>По Москве:</b>\n"
        "• Курьер до станции метро — 500 р.\n"
        "• До адреса в пределах МКАД — 600 р.\n\n"
        "📦 <b>По России:</b>\n"
        "Отправка СДЭК — в среднем 300–400 р. (оплата при получении).\n\n"
        "🎁 <b>При заказе от 2-х комплектов жирных номеров — "
        "доставка СДЭК БЕСПЛАТНО!</b>"
    ),
    "required": (
        "📋 <b>Что нужно для заказа</b>\n\n"
        "Для запуска в производство необходимы:\n\n"
        "1. Ваше <b>ФИО</b>\n"
        "2. <b>Номер телефона</b>\n"
        "3. <b>Адрес СДЭК</b> или способ получения\n"
        "4. <b>Фото СТС с оборотной стороны</b> "
        "(где данные автомобиля написаны буквами и цифрами)"
    ),
    "payment": (
        "💳 <b>Оплата</b>\n\n"
        "Оплата производится официально по предоставленному <b>QR-коду</b> "
        "через приложение вашего банка.\n\n"
        "В назначении платежа обязательно нужно указать слово <b>«НОМЕРА»</b>.\n\n"
        "После оплаты пришлите <b>скриншот чека</b>."
    ),
}


# ─── Открыть FAQ ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "faq:main")
async def faq_main(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        "❓ <b>Часто задаваемые вопросы</b>\n\nВыберите тему:",
        reply_markup=kb_faq(),
        parse_mode="HTML",
    )
    await state.set_state(FAQ.viewing)
    await call.answer()


# ─── Ответы на вопросы ────────────────────────────────────────────────────────

@router.callback_query(FAQ.viewing, F.data.startswith("faq:"))
async def faq_answer(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":")[1]

    if key == "back":
        await call.message.edit_text(
            "Выберите тип покупки:",
            reply_markup=kb_main_menu(),
        )
        await state.set_state(MainMenu.choosing_type)
        await call.answer()
        return

    if key == "main":
        await faq_main(call, state)
        return

    text = FAQ_TEXTS.get(key)
    if not text:
        await call.answer("Раздел не найден.", show_alert=True)
        return

    # Показываем ответ + кнопку вернуться в список FAQ
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад к FAQ", callback_data="faq:main")
    builder.button(text="🏠 Главное меню",  callback_data="faq:back")
    builder.adjust(2)

    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await call.answer()


# ─── FAQ доступен из любого состояния (глобальный хэндлер) ───────────────────
# Зарегистрировать ПОСЛЕ остальных роутеров в bot.py, чтобы не перехватывать.

@router.callback_query(F.data == "faq:main")
async def faq_main_global(call: CallbackQuery, state: FSMContext) -> None:
    """Открыть FAQ из любой точки бота."""
    await call.message.edit_text(
        "❓ <b>Часто задаваемые вопросы</b>\n\nВыберите тему:",
        reply_markup=kb_faq(),
        parse_mode="HTML",
    )
    await state.set_state(FAQ.viewing)
    await call.answer()
