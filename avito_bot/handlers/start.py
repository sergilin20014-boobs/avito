"""
handlers/start.py — /start, обработка диплинка Авито и выбор Опт/Розница.

v3:
  - При /start бот проверяет телефон пользователя в БД.
  - Если телефон найден — подтягивает данные в FSM (пропустит шаг телефона при заказе).
  - Диплинк avito_{chat_id} — сразу к форме заказа.
  - Обычный старт — запрос контакта → проверка Авито-записи или стандартный флоу.
  - FAQ доступен с главного меню.
"""
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext

from states import MainMenu, Catalog, OrderForm
from keyboards import kb_main_menu, kb_phone_request, remove_kb
from handlers.catalog import enter_catalog
from database import upsert_user, get_user_by_phone

logger = logging.getLogger(__name__)
router = Router()


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    args: str = message.text.split(maxsplit=1)[1] if " " in message.text else ""

    # ── Путь 1: диплинк Авито ─────────────────────────────────────────────────
    if args.startswith("avito_"):
        avito_chat_id = args[len("avito_"):]
        await _handle_avito_deeplink(message, state, avito_chat_id)
        return

    # ── Путь 2: обычный старт — создаём/обновляем запись, запрашиваем контакт
    await upsert_user(user_id=user.id, username=user.username)
    await message.answer(
        "👋 Привет! Я помогу оформить заказ на кастомные автономера и рамки.\n\n"
        "Для начала поделитесь номером телефона — это ускорит оформление:",
        reply_markup=kb_phone_request(),
    )
    # Не ставим FSM-состояние сразу — ждём контакт (F.contact)


async def _handle_avito_deeplink(
    message: Message,
    state: FSMContext,
    avito_chat_id: str,
) -> None:
    from database import get_user_by_avito_chat
    avito_record = await get_user_by_avito_chat(avito_chat_id)

    await upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        source="avito",
        avito_chat_id=avito_chat_id,
        avito_shop=avito_record.get("avito_shop") if avito_record else None,
        phone=avito_record.get("phone") if avito_record else None,
        client_type="retail",
    )
    await state.update_data(
        client_type="retail",
        source="avito",
        avito_chat_id=avito_chat_id,
        avito_shop=avito_record.get("avito_shop", "") if avito_record else "",
        category="frames",
        subcategory="f.cls.label",
        product_label="Рамки → Классические рамки → С индивидуальной надписью (+200 руб)",
        quantity=1,
        phone=avito_record.get("phone", "") if avito_record else "",
        _tg_id=message.from_user.id,
    )
    await message.answer(
        "🎨 <b>Наш дизайнер готов сделать 3D-макет рамок!</b>\n\n"
        "Пришлите текст, который нужно разместить на рамке, "
        "или загрузите готовый логотип / референс / дизайн.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    from keyboards import kb_back
    await message.answer("◀️ Навигация:", reply_markup=kb_back())
    await state.set_state(OrderForm.waiting_for_text_or_file)
    logger.info("Deeplink: tg=%s → avito_chat=%s", message.from_user.id, avito_chat_id)


# ─── Получение контакта ───────────────────────────────────────────────────────

@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number or ""
    phone = _normalize_phone(raw)

    await upsert_user(user_id=message.from_user.id, username=message.from_user.username, phone=phone)

    # Ищем в БД совпадение с Авито-записью
    avito_record = await get_user_by_phone(phone)

    if avito_record:
        # Клиент уже оставлял заявку на Авито — пропускаем выбор категорий
        avito_chat_id = avito_record.get("avito_chat_id", "")
        await upsert_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            source="avito",
            avito_chat_id=avito_chat_id,
            avito_shop=avito_record.get("avito_shop"),
            phone=phone,
            client_type="retail",
        )
        await state.update_data(
            client_type="retail",
            source="avito",
            avito_chat_id=avito_chat_id,
            avito_shop=avito_record.get("avito_shop", ""),
            category="frames",
            subcategory="f.cls.label",
            product_label="Рамки → Классические рамки → С индивидуальной надписью (+200 руб)",
            quantity=1,
            phone=phone,
            _tg_id=message.from_user.id,
        )
        await message.answer(
            "✅ Нашли вашу заявку!\n\n"
            "🎨 <b>Наш дизайнер готов сделать 3D-макет!</b>\n\n"
            "Пришлите текст для рамки или загрузите логотип / референс.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        from keyboards import kb_back
        await message.answer("◀️ Навигация:", reply_markup=kb_back())
        await state.set_state(OrderForm.waiting_for_text_or_file)
        logger.info(
            "Contact: tg=%s → avito_chat=%s phone=%s",
            message.from_user.id, avito_chat_id, phone,
        )

    else:
        # Новый клиент — стандартный флоу с меню
        await state.update_data(phone=phone, _tg_id=message.from_user.id)
        await message.answer(
            "👋 Отлично! Теперь выберите тип покупки:",
            reply_markup=remove_kb(),
        )
        await message.answer("⬇️", reply_markup=kb_main_menu())
        await state.set_state(MainMenu.choosing_type)


def _normalize_phone(raw: str) -> str:
    import re
    digits = re.sub(r'\D', '', raw)
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    return digits


# ─── Выбор Опт / Розница ─────────────────────────────────────────────────────

@router.callback_query(MainMenu.choosing_type, F.data.in_({"type:opt", "type:retail"}))
async def choose_type(call: CallbackQuery, state: FSMContext) -> None:
    client_type = "opt" if call.data == "type:opt" else "retail"
    label = "Опт 🏭" if client_type == "opt" else "Розница 🛍️"

    await state.update_data(client_type=client_type)
    await upsert_user(
        user_id=call.from_user.id,
        username=call.from_user.username,
        client_type=client_type,
    )
    await call.message.edit_text(
        f"✅ Выбрано: <b>{label}</b>\n\nОткрываем каталог…",
        parse_mode="HTML",
    )
    await enter_catalog(call, state)
    await call.answer()
