"""
handlers/delivery.py — выбор доставки и сбор данных СДЭК.

Последовательность после СТС:
  Доставка → (СДЭК: ФИО → город → ПВЗ) → телефон → превью
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states import OrderForm
from keyboards import kb_back, kb_delivery

router = Router()


@router.callback_query(OrderForm.choosing_delivery, F.data == "delivery:pickup")
async def delivery_pickup(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(delivery_type="pickup", cdek_track="")
    await call.message.edit_reply_markup(reply_markup=None)
    from handlers.order import _ensure_phone
    await _ensure_phone(call, state)
    await call.answer()


@router.callback_query(OrderForm.choosing_delivery, F.data == "delivery:cdek")
async def delivery_cdek(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(delivery_type="cdek")
    await call.message.edit_text(
        "📦 <b>Доставка СДЭК</b>\n\nВведите ваше ФИО (полностью):",
        parse_mode="HTML",
    )
    await call.message.answer("◀️ Навигация:", reply_markup=kb_back())
    await state.set_state(OrderForm.waiting_for_fio)
    await call.answer()


@router.message(OrderForm.waiting_for_fio, F.text == "◀️ Назад")
async def back_from_fio(message: Message, state: FSMContext) -> None:
    from handlers.order import _ask_delivery
    await _ask_delivery(message, state)


@router.message(OrderForm.waiting_for_fio, F.text)
async def receive_fio(message: Message, state: FSMContext) -> None:
    if message.text == "◀️ Назад":
        return
    await state.update_data(cdek_fio=message.text.strip())
    await message.answer(
        "🏙️ Введите <b>город доставки</b>:",
        parse_mode="HTML",
        reply_markup=kb_back(),
    )
    await state.set_state(OrderForm.waiting_for_city)


@router.message(OrderForm.waiting_for_city, F.text == "◀️ Назад")
async def back_from_city(message: Message, state: FSMContext) -> None:
    await message.answer("Введите ФИО:", reply_markup=kb_back())
    await state.set_state(OrderForm.waiting_for_fio)


@router.message(OrderForm.waiting_for_city, F.text)
async def receive_city(message: Message, state: FSMContext) -> None:
    if message.text == "◀️ Назад":
        return
    await state.update_data(cdek_city=message.text.strip())
    await message.answer(
        "📍 Введите <b>адрес ПВЗ СДЭК</b> (улица, дом):",
        parse_mode="HTML",
        reply_markup=kb_back(),
    )
    await state.set_state(OrderForm.waiting_for_pvz)


@router.message(OrderForm.waiting_for_pvz, F.text == "◀️ Назад")
async def back_from_pvz(message: Message, state: FSMContext) -> None:
    await message.answer("🏙️ Введите город доставки:", reply_markup=kb_back())
    await state.set_state(OrderForm.waiting_for_city)


@router.message(OrderForm.waiting_for_pvz, F.text)
async def receive_pvz(message: Message, state: FSMContext) -> None:
    if message.text == "◀️ Назад":
        return
    await state.update_data(cdek_pvz=message.text.strip(), cdek_track="")
    from handlers.order import _ensure_phone
    await _ensure_phone(message, state)
