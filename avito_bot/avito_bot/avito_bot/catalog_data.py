"""
catalog_data.py — дерево каталога и динамическая генерация inline-клавиатур.

Навигация: на каждом уровне «◀️ Назад» и «🏠 В главное меню».
Листья номеров содержат количество (1 шт. / Комплект 2 шт.).
Рамки — только листья без выбора количества.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

CB_SELECT = "cat:s:"
CB_BACK = "cat:back"
CB_HOME = "cat:home"
CB_MANAGER = "mgr:call"


@dataclass
class CatalogNode:
    id: str
    title: str
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    is_leaf: bool = False
    quantity: Optional[int] = None
    header: str = ""
    category: str = ""  # numbers | frames


NODES: Dict[str, CatalogNode] = {}


def _node(
    node_id: str,
    title: str,
    parent_id: Optional[str] = None,
    *,
    is_leaf: bool = False,
    quantity: Optional[int] = None,
    header: str = "",
    category: str = "",
) -> CatalogNode:
    node = CatalogNode(
        id=node_id,
        title=title,
        parent_id=parent_id,
        is_leaf=is_leaf,
        quantity=quantity,
        header=header,
        category=category,
    )
    NODES[node_id] = node
    if parent_id and parent_id in NODES:
        if node_id not in NODES[parent_id].children:
            NODES[parent_id].children.append(node_id)
    return node


def _link(parent_id: str, child_id: str) -> None:
    if child_id not in NODES[parent_id].children:
        NODES[parent_id].children.append(child_id)
    NODES[child_id].parent_id = parent_id


def _qty(parent_id: str, prefix: str) -> None:
    for qty, label in ((1, "1 шт."), (2, "Комплект 2 шт.")):
        cid = f"{prefix}.q{qty}"
        _node(cid, label, parent_id, is_leaf=True, quantity=qty, category=NODES[parent_id].category)
        _link(parent_id, cid)


def _flags(parent_id: str, prefix: str) -> None:
    variants = (
        ("fl", "С флагом"),
        ("em", "С выбитым флагом"),
        ("eg", "С выбитым флагом и гербом"),
    )
    for code, title in variants:
        fid = f"{prefix}.{code}"
        _node(fid, title, parent_id, category=NODES[parent_id].category)
        _link(parent_id, fid)
        _qty(fid, fid)


def _regular_font_branch(parent_id: str, prefix: str) -> None:
    rid = f"{prefix}.reg"
    _node(rid, "Обычный шрифт", parent_id, category=NODES[parent_id].category)
    _link(parent_id, rid)
    _flags(rid, rid)


def _bold_font_branch(parent_id: str, prefix: str) -> None:
    bid = f"{prefix}.bold"
    _node(bid, "Жирный шрифт", parent_id, category=NODES[parent_id].category)
    _link(parent_id, bid)
    for coat_code, coat_title in (("mat", "Матовый окрас"), ("lac", "Лаковый окрас")):
        cid = f"{bid}.{coat_code}"
        _node(cid, coat_title, bid, category=NODES[parent_id].category)
        _link(bid, cid)
        _flags(cid, cid)


def _std_bold_branches(parent_id: str, prefix: str) -> None:
    _regular_font_branch(parent_id, prefix)
    _bold_font_branch(parent_id, prefix)


def _build_tree() -> None:
    root = _node("root", "Каталог", category="")
    numbers = _node("n", "🔢 Номера", "root", category="numbers")
    frames = _node("f", "🖼️ Рамки", "root", category="frames")
    _link("root", "n")
    _link("root", "f")

    # ── Номера ────────────────────────────────────────────────────────────────
    branches = (
        ("n.st", "Стандартный номер"),
        ("n.sq", "Квадратный номер (Япония / США)"),
        ("n.mo", "Мотономер"),
        ("n.fr", "Иностранный номер"),
        ("n.tr", "Тракторный номер / Спецтехника"),
        ("n.sv", "Сувенирные номера"),
    )
    for bid, title in branches:
        _node(bid, title, "n", category="numbers")
        _link("n", bid)

    for bid in ("n.st", "n.sq", "n.mo"):
        _std_bold_branches(bid, bid)

    # Спецномера
    sp = _node("n.sp", "Спецномера", "n", category="numbers")
    _link("n", "n.sp")
    for code, title in (
        ("taxi", "Такси"),
        ("mvd", "МВД"),
        ("arm", "Военные"),
        ("dip", "Дипломатические"),
    ):
        sid = f"n.sp.{code}"
        _node(sid, title, "n.sp", category="numbers")
        _link("n.sp", sid)
        _std_bold_branches(sid, sid)

    # Иностранный: без флагов
    fr = "n.fr"
    fr_reg = _node(f"{fr}.reg", "Стандартный шрифт", fr, category="numbers")
    _link(fr, f"{fr}.reg")
    _qty(f"{fr}.reg", f"{fr}.reg")
    fr_bold = _node(f"{fr}.bold", "Жирный шрифт", fr, category="numbers")
    _link(fr, f"{fr}.bold")
    for coat_code, coat_title in (("mat", "Матовый окрас"), ("lac", "Лаковый окрас")):
        cid = f"{fr_bold.id}.{coat_code}"
        _node(cid, coat_title, fr_bold.id, category="numbers")
        _link(fr_bold.id, cid)
        _qty(cid, cid)

    # Тракторный
    tr = "n.tr"
    tr_reg = _node(f"{tr}.reg", "Стандартный шрифт", tr, category="numbers")
    _link(tr, f"{tr}.reg")
    _qty(f"{tr}.reg", f"{tr}.reg")
    tr_bold = _node(f"{tr}.bold", "Жирный шрифт", tr, category="numbers")
    _link(tr, f"{tr}.bold")
    _qty(f"{tr}.bold", f"{tr}.bold")

    # Сувенирные
    sv = "n.sv"
    for code, title in (("pr", "Напечатанный"), ("em", "Выдавленный")):
        sid = f"{sv}.{code}"
        _node(sid, title, sv, category="numbers")
        _link(sv, sid)
        _qty(sid, sid)

    # ── Рамки (без количества) ───────────────────────────────────────────────
    cls = _node("f.cls", "Классические рамки", "f", category="frames")
    _link("f", "f.cls")
    for code, title in (("plain", "Без надписи"), ("label", "С индивидуальной надписью (+200 руб)")):
        lid = f"f.cls.{code}"
        _node(lid, title, "f.cls", is_leaf=True, category="frames")
        _link("f.cls", lid)

    led = _node(
        "f.led",
        "LED рамки (с подсветкой)",
        "f",
        category="frames",
        header="💡 Нанесение индивидуальной надписи бесплатно!",
    )
    _link("f", "f.led")
    _node(
        "f.led.label",
        "С индивидуальной надписью",
        "f.led",
        is_leaf=True,
        category="frames",
        header="💡 Нанесение индивидуальной надписи бесплатно!",
    )
    _link("f.led", "f.led.label")

    mag = _node("f.mag", "Магнитные рамки", "f", category="frames")
    _link("f", "f.mag")
    _node("f.mag.plain", "Без надписи", "f.mag", is_leaf=True, category="frames")
    _link("f.mag", "f.mag.plain")


_build_tree()


def get_node(node_id: str) -> Optional[CatalogNode]:
    return NODES.get(node_id)


def get_parent_id(node_id: str) -> Optional[str]:
    node = NODES.get(node_id)
    return node.parent_id if node else None


def get_breadcrumb(node_id: str) -> str:
    parts: List[str] = []
    current = node_id
    while current and current in NODES:
        parts.append(NODES[current].title)
        current = NODES[current].parent_id or ""
        if current == "root":
            break
    return " → ".join(reversed(parts))


def get_product_label(node_id: str) -> str:
    return get_breadcrumb(node_id)


def is_numbers_product(node_id: str) -> bool:
    node = NODES.get(node_id)
    return bool(node and node.category == "numbers")


def build_catalog_keyboard(node_id: str) -> InlineKeyboardMarkup:
    node = NODES[node_id]
    builder = InlineKeyboardBuilder()

    for child_id in node.children:
        child = NODES[child_id]
        builder.button(text=child.title, callback_data=f"{CB_SELECT}{child_id}")

    if node_id != "root":
        builder.button(text="◀️ Назад", callback_data=CB_BACK)
    builder.button(text="🏠 В главное меню", callback_data=CB_HOME)
    builder.button(text="👤 Позвать менеджера", callback_data=CB_MANAGER)

    builder.adjust(1)
    return builder.as_markup()


def render_menu(node_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    node = NODES[node_id]
    lines = [f"<b>{node.title}</b>"]
    if node.header:
        lines.append("")
        lines.append(node.header)
    if node_id == "root":
        lines.append("")
        lines.append("Выберите категорию товара:")
    elif node.children and not node.is_leaf:
        lines.append("")
        lines.append("Выберите вариант:")
    elif node.is_leaf:
        crumb = get_breadcrumb(node_id)
        lines = [f"✅ <b>Выбрано:</b> {crumb}"]

    text = "\n".join(lines)
    if node.is_leaf:
        return text, InlineKeyboardMarkup(inline_keyboard=[])
    return text, build_catalog_keyboard(node_id)


def parse_select_callback(data: str) -> Optional[str]:
    if data.startswith(CB_SELECT):
        return data[len(CB_SELECT):]
    return None
