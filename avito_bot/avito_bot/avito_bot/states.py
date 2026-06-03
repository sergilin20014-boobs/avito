"""
states.py — FSM-состояния для aiogram 3.x.
"""
from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    choosing_type = State()


class Catalog(StatesGroup):
    browsing = State()


class FAQ(StatesGroup):
    viewing = State()


class OrderForm(StatesGroup):
    waiting_for_text_or_file = State()
    waiting_for_sts = State()
    choosing_delivery = State()
    waiting_for_fio = State()
    waiting_for_phone = State()
    waiting_for_city = State()
    waiting_for_pvz = State()
    confirming_order = State()
