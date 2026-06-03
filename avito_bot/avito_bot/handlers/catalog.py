"""
handlers/catalog.py — динамическое дерево каталога с универсальной навигацией.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from states import Catalog, OrderForm, MainMenu
from catalog_data import (
    NODES,
    CB_BACK,
    CB_HOME,
    CB_SELECT,
    build_catalog_keyboard,
    get_node,
    get_parent_id,
    get_product_label,
    parse_select_callback,
    render_menu,
)
from keyboards import kb_main_menu, kb_skip_file, kb_back, remove_kb

router = Router()


async def _show_node(
    target: CallbackQuery | Message,
    state: FSMContext,
    node_id: str,
    *,
    edit: bool = False,
) -> None:
    text, markup = render_menu(node_id)
    await state.update_data(catalog_node=node_id)

    if isinstance(target, CallbackQuery):
        if edit and not get_node(node_id).is_leaf:
            await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await target.message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")

    if node_id != "root":
        await _ensure_back_reply(target)


async def _ensure_back_reply(target: CallbackQuery | Message) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    await message.answer("◀️ Навигация:", reply_markup=kb_back())


async def _start_order_form(target: CallbackQuery, state: FSMContext, leaf_id: str) -> None:
    node = get_node(leaf_id)
    if not node or not node.is_leaf:
        await target.answer("Выберите конкретный товар.", show_alert=True)
        return

    category = node.category
    qty = node.quantity or 1
    label = get_product_label(leaf_id)

    await state.update_data(
        category=category,
        subcategory=leaf_id,
        product_label=label,
        quantity=qty,
    )

    await target.message.edit_text(
        f"✅ <b>Выбрано:</b> {label}\n\n"
        "Пришлите текст для плашки / госномер или загрузите референс / логотип / дизайн.\n"
        "Можно прикрепить фото, документ или написать текст.",
        reply_markup=kb_skip_file(),
        parse_mode="HTML",
    )
    await target.message.answer("◀️ Навигация:", reply_markup=kb_back())
    await state.set_state(OrderForm.waiting_for_text_or_file)
    await target.answer()


@router.callback_query(Catalog.browsing)
async def catalog_select(call: CallbackQuery, state: FSMContext) -> None:
    """Глобальный обработчик навигации по каталогу."""
    # Логируем для отладки, чтобы увидеть, что прилетело в call.data
    logger.info(f"=== МЫ ВНУТРИ ХЕНДЛЕРА КАТАЛОГА! call.data: {call.data} ===")
    
    await call.answer()
    
    if call.data == CB_BACK:
        data = await state.get_data()
        current = data.get("catalog_node", "root")
        parent = get_parent_id(current)
        if not parent or current == "root":
            await call.message.edit_text("Выберите тип покупки:", reply_markup=kb_main_menu())
            await state.set_state(MainMenu.choosing_type)
            return
        await _show_node(call, state, parent, edit=True)
        return

    if call.data == CB_HOME:
        await call.message.edit_text("Выберите тип покупки:", reply_markup=kb_main_menu())
        await state.set_state(MainMenu.choosing_type)
        return

    # Ловим выбор категории/подкатегории
    node_id = parse_select_callback(call.data)
    if not node_id:
        # Если префикс кента не распарсился, пробуем забрать весь data как id узла
        node_id = call.data.replace("cat:s:", "").replace("cat:", "")
        
    if node_id in NODES:
        node = NODES[node_id]
        if node.is_leaf:
            # Если это конечный товар — переводим на оформление заказа
            await state.update_data(subcategory=node_id, category=get_parent_id(node_id) or "numbers")
            await call.message.delete()
            from handlers.order import start_order_flow
            await start_order_flow(call.message, state)
        else:
            # Иначе прем дальше по дереву каталога
            await _show_node(call, state, node_id, edit=True)
    else:
        logger.warning(f"Узел каталога не найден в NODES: {node_id}")


@router.callback_query(Catalog.browsing, F.data == CB_BACK)
async def catalog_back(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    current = data.get("catalog_node", "root")
    parent = get_parent_id(current)

    if not parent or current == "root":
        await call.message.edit_text(
            "Выберите тип покупки:",
            reply_markup=kb_main_menu(),
            parse_mode="HTML",
        )
        await call.message.answer("◀️ Навигация:", reply_markup=remove_kb())
        await state.set_state(MainMenu.choosing_type)
        await call.answer()
        return

    await _show_node(call, state, parent, edit=True)
    await call.answer()


@router.callback_query(Catalog.browsing, F.data == CB_HOME)
async def catalog_home(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    phone = data.get("phone")
    client_type = data.get("client_type")
    source = data.get("source")
    avito_chat_id = data.get("avito_chat_id")
    avito_shop = data.get("avito_shop")

    await state.clear()
    if phone:
        await state.update_data(phone=phone)
    if client_type:
        await state.update_data(client_type=client_type)
    if source:
        await state.update_data(source=source, avito_chat_id=avito_chat_id, avito_shop=avito_shop)

    await call.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите тип покупки:",
        reply_markup=kb_main_menu(),
        parse_mode="HTML",
    )
    await call.message.answer("◀️ Навигация:", reply_markup=remove_kb())
    await state.set_state(MainMenu.choosing_type)
    await call.answer()


@router.message(Catalog.browsing, F.text == "◀️ Назад")
async def catalog_back_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current = data.get("catalog_node", "root")
    parent = get_parent_id(current)

    if not parent or current == "root":
        await message.answer(
            "Выберите тип покупки:",
            reply_markup=kb_main_menu(),
        )
        await message.answer("◀️ Навигация:", reply_markup=remove_kb())
        await state.set_state(MainMenu.choosing_type)
        return

    await _show_node(message, state, parent)

@router.callback_query(F.data.startswith("type:"))
async def enter_catalog(message_or_call, state: FSMContext) -> None:
    """Точка входа в каталог после выбора Опт/Розница."""
    # Сразу жестко переводим в стейт каталога, чтобы снять блокировку
    await state.set_state(Catalog.browsing)
    await state.update_data(catalog_node="root")

    if isinstance(message_or_call, CallbackQuery):
        await message_or_call.answer()
        await message_or_call.message.edit_text(
            "📦 <b>Каталог</b>\n\nВыберите категорию товара:",
            reply_markup=build_catalog_keyboard("root"),
            parse_mode="HTML",
        )
        await message_or_call.message.answer("◀️ Навигация:", reply_markup=kb_back())
    else:
        await message_or_call.answer(
            "📦 <b>Каталог</b>\n\nВыберите категорию товара:",
            reply_markup=build_catalog_keyboard("root"),
            parse_mode="HTML",
        )
        await message_or_call.answer("◀️ Навигация:", reply_markup=kb_back())               

    await state.update_data(catalog_node="root")
    await state.set_state(Catalog.browsing)
