"""
bot.py — точка входа Telegram-бота.

v3: добавлены роутеры faq и manager.
    Порядок регистрации роутеров критичен — manager должен быть первым,
    чтобы «mgr:call» перехватывался раньше, чем любой state-фильтр.
"""
import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from logging_setup import setup_logging

setup_logging()

from config import config
from database import init_db
from middlewares.error_handler import global_error_handler
from middlewares.update_logger import UpdateLoggingMiddleware
from handlers import start, catalog, order, delivery, admin
from handlers import faq, manager       # новые роутеры v3
from services.avito import identify_shop, handle_avito_logic

logger = logging.getLogger(__name__)

WEBHOOK_PORT = 8080


def make_avito_webhook_handler(bot: Bot):
    async def avito_webhook_handler(request: web.Request) -> web.Response:
        secret = (
            request.headers.get("X-Avito-Signature")
            or request.rel_url.query.get("token", "")
        )
        shop = identify_shop(secret)
        if not shop:
            logger.warning("Webhook: неизвестный секрет %r", secret[:16] + "…" if len(secret) > 16 else secret)
            return web.Response(status=403, text="Unknown shop")

        try:
            payload = await request.json()
        except Exception as e:
            logger.error("Webhook: некорректный JSON — %s", e)
            return web.Response(status=400, text="Bad JSON")

        event_type = payload.get("type", "")
        chat_id = payload.get("value", {}).get("chat_id", "")
        logger.info("Webhook: shop=%s event=%s chat=%s", shop["name"], event_type, chat_id or "—")

        if event_type == "chatMessage":
            asyncio.create_task(
                handle_avito_logic(
                    bot=bot,
                    payload=payload,
                    shop_name=shop["name"],
                    account_token=shop["token"],
                )
            )
        return web.Response(status=200, text="OK")
    return avito_webhook_handler


async def start_webhook_server(bot: Bot) -> web.AppRunner:
    app = web.Application()
    app.router.add_post("/webhooks/avito", make_avito_webhook_handler(bot))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logger.info(f"Webhook-сервер: http://0.0.0.0:{WEBHOOK_PORT}/webhooks/avito")
    return runner


async def main() -> None:
    await init_db()
    logger.info("БД инициализирована.")

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(UpdateLoggingMiddleware())

    dp.errors.register(global_error_handler)

    # ── Порядок роутеров важен ────────────────────────────────────────────────
    # manager — первым, чтобы mgr:call срабатывал из любого FSM-состояния
    dp.include_router(manager.router)
    dp.include_router(faq.router)
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(delivery.router)
    dp.include_router(order.router)
    dp.include_router(admin.router)

    webhook_runner = await start_webhook_server(bot)

    logger.info("Бот запущен. Polling + Webhook работают параллельно...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await webhook_runner.cleanup()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
