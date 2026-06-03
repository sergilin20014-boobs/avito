"""
keyboards.py — фабрики клавиатур.

v3: изменения:
  - kb_back()         — Reply-кнопка «◀️ Назад» (всегда видна внизу экрана)
  - kb_call_manager() — Inline-кнопка «👤 Позвать менеджера» (вставляется рядом с любым inline-блоком)
  - kb_main_menu()    — главное меню с кнопкой FAQ
  - kb_numbers_subcategory() / kb_frames_subcategory() — актуальный каталог с ценами
  - kb_phone_request() — запрос телефона через inline (request_contact недоступен в inline,
                         используем ReplyKeyboard с request_contact)
"""
from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ─── Универсальная Reply-кнопка «Назад» ──────────────────────────────────────
# Показывается внизу экрана на всех шагах кроме главного меню.

def kb_back() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="◀️ Назад")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ─── Inline-кнопка «Позвать менеджера» ───────────────────────────────────────
# Добавляется к любому inline-блоку через .attach() или отдельным сообщением.

def kb_call_manager() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Позвать менеджера", callback_data="mgr:call")
    return builder.as_markup()


def _with_manager(builder: InlineKeyboardBuilder) -> InlineKeyboardMarkup:
    """Добавляет кнопку менеджера последней строкой к любому builder'у."""
    builder.button(text="👤 Позвать менеджера", callback_data="mgr:call")
    return builder.as_markup()


# ─── Главное меню ─────────────────────────────────────────────────────────────

def kb_main_menu() -> InlineKeyboardMarkup:
    """Главное меню с выбором Опт/Розница и кнопкой FAQ."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏭 Опт",      callback_data="type:opt")
    builder.button(text="🛍️ Розница", callback_data="type:retail")
    builder.button(text="❓ Часто задаваемые вопросы (FAQ)", callback_data="faq:main")
    builder.adjust(2, 1)
    return builder.as_markup()


# Алиас для обратной совместимости с handlers/start.py
def kb_client_type() -> InlineKeyboardMarkup:
    return kb_main_menu()


# ─── Каталог: разделы ─────────────────────────────────────────────────────────

def kb_categories() -> InlineKeyboardMarkup:
    """Устаревший алиас — каталог строится динамически в catalog_data."""
    from catalog_data import build_catalog_keyboard
    return build_catalog_keyboard("root")


# ─── Каталог: генерируется динамически в catalog_data.py ─────────────────────

def kb_numbers_subcategory() -> InlineKeyboardMarkup:
    from catalog_data import build_catalog_keyboard
    return build_catalog_keyboard("n")


def kb_frames_subcategory() -> InlineKeyboardMarkup:
    from catalog_data import build_catalog_keyboard
    return build_catalog_keyboard("f")


# ─── Форма заказа ─────────────────────────────────────────────────────────────

def kb_skip_file() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭️ Пропустить",        callback_data="skip:file")
    builder.button(text="👤 Позвать менеджера", callback_data="mgr:call")
    builder.adjust(1)
    return builder.as_markup()


def kb_delivery() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏪 Самовывоз",         callback_data="delivery:pickup")
    builder.button(text="📦 Доставка СДЭК",     callback_data="delivery:cdek")
    builder.button(text="👤 Позвать менеджера", callback_data="mgr:call")
    builder.adjust(2, 1)
    return builder.as_markup()


def kb_skip_doc() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭️ Пропустить верификацию", callback_data="skip:doc")
    builder.button(text="👤 Позвать менеджера",       callback_data="mgr:call")
    builder.adjust(1)
    return builder.as_markup()


def kb_confirm_order() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить заказ", callback_data="order:confirm")
    builder.button(text="❌ Отменить",           callback_data="order:cancel")
    builder.adjust(2)
    return builder.as_markup()


def kb_phone_request() -> ReplyKeyboardMarkup:
    """Reply-кнопка запроса контакта (request_contact работает только в Reply)."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📱 Отправить мой номер телефона", request_contact=True),
        ]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── FAQ ──────────────────────────────────────────────────────────────────────

def kb_faq() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚖️ Законность и ГОСТ",        callback_data="faq:law")
    builder.button(text="🏭 Изготовление и самовывоз", callback_data="faq:pickup")
    builder.button(text="🚚 Доставка",                  callback_data="faq:delivery")
    builder.button(text="📋 Что нужно для заказа",     callback_data="faq:required")
    builder.button(text="💳 Оплата",                    callback_data="faq:payment")
    builder.button(text="◀️ В главное меню",            callback_data="faq:back")
    builder.adjust(1)
    return builder.as_markup()


# ─── Авито: остаться / перейти в бот ─────────────────────────────────────────

def kb_avito_choice(avito_chat_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Оформить здесь",   callback_data="avito:bot")
    builder.button(text="💬 Остаться на Авито", url=avito_chat_url)
    builder.adjust(1)
    return builder.as_markup()


# ─── Админ-панель ─────────────────────────────────────────────────────────────

def kb_admin_order(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏭 Переслать на производство",
        callback_data=f"admin:forward:{order_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
