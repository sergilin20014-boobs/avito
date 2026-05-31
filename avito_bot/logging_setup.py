"""
logging_setup.py — единая настройка логов для всего проекта.

Файлы: logs/bot.log с ротацией.
Консоль: цветной вывод (Windows 10+ / Linux).

Шумные библиотеки (aiogram, aiohttp) приглушены до WARNING.
Особо важно: aiogram.event логирует каждый апдейт на уровне INFO —
мы заглушаем его отдельно, чтобы наш UpdateLoggingMiddleware
был единственным источником информации об обновлениях.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOG_BACKUP_COUNT, LOG_DIR, LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
CONSOLE_FORMAT = "%(asctime)s | %(levelname_colored)s | %(name)s | %(message)s"

# Логгеры, которые глушим до WARNING — они дают бесполезный шум
NOISY_LOGGERS = (
    "aiogram",           # включая aiogram.event — ключевой источник мусорных строк
    "aiogram.event",     # явно, на случай если aiogram меняет иерархию
    "aiohttp",
    "asyncio",
    "urllib3",
    "google",
    "gspread",
    "httpx",
)


class _Colors:
    GREY = "\033[90m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


_LEVEL_COLORS = {
    logging.DEBUG:    _Colors.GREY,
    logging.INFO:     _Colors.GREEN,
    logging.WARNING:  _Colors.YELLOW,
    logging.ERROR:    _Colors.RED,
    logging.CRITICAL: _Colors.RED + _Colors.BOLD,
}


def _enable_windows_ansi() -> None:
    if sys.platform != "win32":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


class BotFormatter(logging.Formatter):
    colored: bool = False

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, _Colors.RESET)
        if self.colored:
            record.levelname_colored = f"{color}{record.levelname:<8}{_Colors.RESET}"
        else:
            record.levelname_colored = f"{record.levelname:<8}"
        return super().format(record)


def setup_logging() -> None:
    """Инициализирует root-logger. Безопасно вызывать повторно."""
    if getattr(setup_logging, "_done", False):
        return

    root = logging.getLogger()
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root.setLevel(level)

    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_FILE

    # ── Файловый хэндлер ──────────────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(BotFormatter(FILE_FORMAT, datefmt=DATE_FORMAT))

    # ── Консольный хэндлер ────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    _enable_windows_ansi()
    console_fmt = BotFormatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT)
    console_fmt.colored = True
    console_handler.setFormatter(console_fmt)

    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # ── Глушим шумные логгеры ─────────────────────────────────────────────────
    # ВАЖНО: propagate=False + уровень WARNING — двойная защита.
    # Только propagate=False недостаточно если где-то добавляют хэндлеры напрямую.
    for name in NOISY_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(logging.WARNING)
        lg.propagate = True  # пусть WARNING/ERROR всё же долетают до root

    setup_logging._done = True  # type: ignore[attr-defined]

    logging.getLogger(__name__).info(
        "Логирование запущено: level=%s, файл=%s",
        LOG_LEVEL.upper(),
        log_path.resolve(),
    )