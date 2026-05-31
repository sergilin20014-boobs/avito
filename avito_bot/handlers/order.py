"""
handlers/order.py — линейная форма заказа.

Последовательность:
  Каталог → Макет/текст → СТС → Доставка → Телефон (если нужен) → Превью → Подтверждение
"""
import logging
import re

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import OrderForm, Catalog
from catalog_data import get_parent_id, build_catalog_keyboard, get_product_label
from keyboards import (
    kb_delivery, kb_skip_doc, kb_confirm_order,
    kb_skip_file, kb_phone_request, kb_back, remove_kb,
)
from database import create_order, upsert_user
from handlers.admin import notify_admin_new_order
from services.sheets import append_order_to_sheet

logger = logging.getLogger(__name__)
router = Router()

_STS_TEXT = (
    "📄 <b>Фото СТС (оборотная сторона)</b>\n\n"
    "Пришлите фото СТС с оборотной стороны — там данные автомобиля написаны "
    "буквами и цифрами. Это нужно для запуска номера в производство.\n\n"
    "<i>Можно пропустить, если СТС нет под рукой.</i>"
)


# ─── Шаг 1: макет / текст ─────────────────────────────────────────────────────

@router.message(OrderForm.waiting_for_text_or_file, F.text == "◀️ Назад")
async def back_from_design(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sub = data.get("subcategory", "")
    parent = get_parent_id(sub) or "root"
    text = f"✅ <b>Выбрано:</b> {get_product_label(sub)}\n\nВернулись к выбору варианта."
    if parent == "root":
        await message.answer(
            "📦 <b>Каталог</b>\n\nВыберите категорию товара:",
            reply_markup=build_catalog_keyboard("root"),
            parse_mode="HTML",
        )
        await state.update_data(catalog_node="root")
    else:
        await message.answer(
            text,
            reply_markup=build_catalog_keyboard(parent),
            parse_mode="HTML",
        )
        await state.update_data(catalog_node=parent)
    await message.answer("◀️ Навигация:", reply_markup=kb_back())
    await state.set_state(Catalog.browsing)


@router.message(OrderForm.waiting_for_text_or_file, F.text)
async def receive_plate_text(message: Message, state: FSMContext) -> None:
    if message.text == "◀️ Назад":
        return
    await state.update_data(plate_text=message.text, file_id=None)
    await _ask_sts(message, state)


@router.message(OrderForm.waiting_for_text_or_file, F.photo | F.document | F.video)
async def receive_plate_file(message: Message, state: FSMContext) -> None:
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        else:
            file_id = message.video.file_id
        await state.update_data(plate_text=message.caption or "", file_id=file_id)
        await _ask_sts(message, state)
    except Exception as e:
        logger.exception("Ошибка приёма файла макета: %s", e)
        await message.answer(
            "⚠️ Не удалось принять файл. Попробуйте ещё раз или отправьте текст.",
            reply_markup=kb_skip_file(),
        )


@router.callback_query(OrderForm.waiting_for_text_or_file, F.data == "skip:file")
async def skip_plate_file(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(plate_text="", file_id=None)
    await call.message.edit_reply_markup(reply_markup=None)
    await _ask_sts(call.message, state)
    await call.answer()


# ─── Шаг 2: СТС ───────────────────────────────────────────────────────────────

async def _ask_sts(target: Message, state: FSMContext) -> None:
    await target.answer(_STS_TEXT, reply_markup=kb_skip_doc(), parse_mode="HTML")
    await state.set_state(OrderForm.waiting_for_sts)


@router.message(OrderForm.waiting_for_sts, F.text == "◀️ Назад")
async def back_from_sts(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Пришлите текст для плашки / госномер или загрузите референс / дизайн:",
        reply_markup=kb_skip_file(),
    )
    await state.set_state(OrderForm.waiting_for_text_or_file)


@router.message(OrderForm.waiting_for_sts, F.photo | F.document)
async def receive_sts_photo(message: Message, state: FSMContext) -> None:
    try:
        if message.photo:
            doc_file_id = message.photo[-1].file_id
        elif message.document:
            doc_file_id = message.document.file_id
        else:
            await message.answer("Пришлите фото или документ СТС.", reply_markup=kb_skip_doc())
            return
        await state.update_data(doc_file_id=doc_file_id)
        await message.answer("✅ СТС получено!")
        await _ask_delivery(message, state)
    except Exception as e:
        logger.exception("Ошибка приёма СТС: %s", e)
        await message.answer(
            "⚠️ Не удалось обработать файл. Попробуйте другое фото или нажмите «Пропустить».",
            reply_markup=kb_skip_doc(),
        )


@router.callback_query(OrderForm.waiting_for_sts, F.data == "skip:doc")
async def skip_sts(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(doc_file_id=None)
    await call.message.edit_reply_markup(reply_markup=None)
    await _ask_delivery(call.message, state)
    await call.answer()


# ─── Шаг 3: доставка ──────────────────────────────────────────────────────────

async def _ask_delivery(message: Message, state: FSMContext) -> None:
    await message.answer(
        "🚚 <b>Выберите способ доставки:</b>",
        reply_markup=kb_delivery(),
        parse_mode="HTML",
    )
    await state.set_state(OrderForm.choosing_delivery)


@router.message(OrderForm.choosing_delivery, F.text == "◀️ Назад")
async def back_from_delivery(message: Message, state: FSMContext) -> None:
    await _ask_sts(message, state)


# ─── Шаг 4: телефон ───────────────────────────────────────────────────────────

async def _ensure_phone(event: CallbackQuery | Message, state: FSMContext) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    data = await state.get_data()
    phone = data.get("phone")

    if phone:
        await _finalize_before_summary(message, state)
        return

    await message.answer(
        "📱 Для подтверждения заказа отправьте номер телефона, нажав кнопку ниже:",
        reply_markup=kb_phone_request(),
    )
    await state.set_state(OrderForm.waiting_for_phone)


@router.message(OrderForm.waiting_for_phone, F.text == "◀️ Назад")
async def back_from_phone(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("delivery_type") == "cdek" and data.get("cdek_pvz"):
        await message.answer(
            "📍 Введите адрес ПВЗ СДЭК (улица, дом):",
            reply_markup=kb_back(),
        )
        await state.set_state(OrderForm.waiting_for_pvz)
    elif data.get("delivery_type") == "cdek" and data.get("cdek_city"):
        await message.answer("🏙️ Введите город доставки:", reply_markup=kb_back())
        await state.set_state(OrderForm.waiting_for_city)
    elif data.get("delivery_type") == "cdek" and data.get("cdek_fio"):
        await message.answer("Введите ФИО:", reply_markup=kb_back())
        await state.set_state(OrderForm.waiting_for_fio)
    else:
        await _ask_delivery(message, state)


@router.message(OrderForm.waiting_for_phone, F.contact)
async def receive_phone_contact(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number or ""
    phone = _normalize_phone(raw)
    await state.update_data(phone=phone)
    await upsert_user(user_id=message.from_user.id, username=message.from_user.username, phone=phone)
    await message.answer("✅ Телефон сохранён!", reply_markup=remove_kb())
    await _finalize_before_summary(message, state)


@router.message(OrderForm.waiting_for_phone, F.text)
async def receive_phone_text(message: Message, state: FSMContext) -> None:
    if message.text == "◀️ Назад":
        return
    match = re.search(
        r"(?:\+7|8)[\s\(-]*\d{3}[\s\)-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}|\b9\d{9}\b",
        message.text,
    )
    if not match:
        await message.answer(
            "❌ Не удалось распознать номер. Формат: +7 999 123-45-67 "
            "или нажмите «Отправить мой номер».",
            reply_markup=kb_phone_request(),
        )
        return
    phone = _normalize_phone(match.group(0))
    await state.update_data(phone=phone)
    await upsert_user(user_id=message.from_user.id, username=message.from_user.username, phone=phone)
    await message.answer("✅ Телефон сохранён!", reply_markup=remove_kb())
    await _finalize_before_summary(message, state)


async def _finalize_before_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("delivery_type") == "cdek" and not data.get("cdek_track"):
        track = await _create_cdek_track(state)
        await state.update_data(cdek_track=track)
        if track and track not in ("ERR_AUTH", "ERR_CREATE"):
            await message.answer(
                f"📦 Предварительный трек СДЭК: <code>{track}</code>",
                parse_mode="HTML",
            )
    await _show_summary(message, state)


async def _create_cdek_track(state: FSMContext) -> str:
    from services.cdek import create_cdek_draft

    data = await state.get_data()
    return await create_cdek_draft(
        fio=data.get("cdek_fio", ""),
        phone=data.get("phone", ""),
        city=data.get("cdek_city", ""),
        pvz_address=data.get("cdek_pvz", ""),
        order_comment=data.get("plate_text", ""),
    )


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return digits


# ─── Итоговая карточка ────────────────────────────────────────────────────────

async def _show_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    product = data.get("product_label") or get_product_label(data.get("subcategory", ""))
    client_type = "Опт" if data.get("client_type") == "opt" else "Розница"
    delivery = "Самовывоз" if data.get("delivery_type") == "pickup" else "СДЭК"
    plate = data.get("plate_text") or "—"
    phone = data.get("phone") or "—"
    has_file = "✅ Загружен" if data.get("file_id") else "—"
    has_doc = "✅ Загружен" if data.get("doc_file_id") else "—"
    qty = data.get("quantity", 1)
    qty_line = f"\n🔢 Количество: {qty} шт." if data.get("category") == "numbers" else ""

    cdek_block = ""
    if data.get("delivery_type") == "cdek":
        cdek_block = (
            f"\n👤 ФИО: {data.get('cdek_fio', '—')}"
            f"\n🏙️ Город: {data.get('cdek_city', '—')}"
            f"\n📍 ПВЗ: {data.get('cdek_pvz', '—')}"
        )
        if data.get("cdek_track"):
            cdek_block += f"\n📦 Трек: <code>{data['cdek_track']}</code>"

    summary = (
        f"📋 <b>Ваш заказ — проверьте данные:</b>\n\n"
        f"🛍️ Тип: {client_type}\n"
        f"🏷️ Товар: {product}"
        f"{qty_line}\n"
        f"✍️ Текст плашки: {plate}\n"
        f"🎨 Дизайн/файл: {has_file}\n"
        f"📄 СТС/ПТС: {has_doc}\n"
        f"📞 Телефон: {phone}\n"
        f"🚚 Доставка: {delivery}"
        f"{cdek_block}"
    )

    await message.answer(summary, reply_markup=kb_confirm_order(), parse_mode="HTML")
    await message.answer("◀️ Навигация:", reply_markup=kb_back())
    await state.set_state(OrderForm.confirming_order)


@router.message(OrderForm.confirming_order, F.text == "◀️ Назад")
async def back_from_confirm(message: Message, state: FSMContext) -> None:
    await _ensure_phone(message, state)


# ─── Подтверждение / отмена ───────────────────────────────────────────────────

@router.callback_query(OrderForm.confirming_order, F.data == "order:confirm")
async def confirm_order(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    qty = data.get("quantity", 1)
    product_label = data.get("product_label") or get_product_label(data.get("subcategory", ""))

    order_data = {
        "user_id": call.from_user.id,
        "username": call.from_user.username or str(call.from_user.id),
        "client_type": data.get("client_type", "retail"),
        "source": data.get("source", "telegram"),
        "avito_shop": data.get("avito_shop", ""),
        "avito_chat_id": data.get("avito_chat_id", ""),
        "category": data.get("category", ""),
        "subcategory": data.get("subcategory", ""),
        "plate_text": (
            f"[x{qty}] {data.get('plate_text', '')}".strip()
            if data.get("category") == "numbers"
            else data.get("plate_text", "")
        ) or product_label,
        "file_id": data.get("file_id", ""),
        "delivery_type": data.get("delivery_type", "pickup"),
        "cdek_fio": data.get("cdek_fio", ""),
        "cdek_phone": data.get("phone", ""),
        "cdek_city": data.get("cdek_city", ""),
        "cdek_pvz": data.get("cdek_pvz", ""),
        "cdek_track": data.get("cdek_track", ""),
        "doc_file_id": data.get("doc_file_id", ""),
        "status": "new",
    }

    order_id = await create_order(order_data)
    order_data["id"] = order_id
    order_data["product_label"] = product_label
    order_data["quantity"] = qty

    logger.info(
        "Заказ #%s создан: user=%s source=%s delivery=%s",
        order_id, call.from_user.id, order_data["source"], order_data["delivery_type"],
    )

    await call.message.edit_text(
        f"✅ <b>Заказ #{order_id} принят!</b>\n\n"
        "Менеджер свяжется с вами в ближайшее время.\n"
        + (
            f"📦 Трек СДЭК: <code>{data.get('cdek_track')}</code>"
            if data.get("cdek_track") else ""
        ),
        parse_mode="HTML",
        reply_markup=None,
    )
    await call.message.answer("🏁 Готово!", reply_markup=remove_kb())

    await notify_admin_new_order(bot, order_data)

    try:
        await append_order_to_sheet(order_data)
    except Exception as e:
        logger.error("Ошибка записи заказа в Sheets: %s", e)

    await state.clear()
    await call.answer("Заказ оформлен!")


@router.callback_query(OrderForm.confirming_order, F.data == "order:cancel")
async def cancel_order(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Заказ отменён. Напишите /start чтобы начать заново.")
    await call.message.answer("🏁", reply_markup=remove_kb())
    await call.answer()
