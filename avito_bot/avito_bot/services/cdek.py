"""
services/cdek.py — интеграция с API СДЭК v2.
MVP: авторизация рабочая (OAuth2), создание черновика — заглушка с рандомным трек-номером.
Для продакшена: раскомментировать реальный POST-запрос к /orders.
"""
import random
import string
import logging
import aiohttp
from config import CDEK_API_URL, CDEK_CLIENT_ID, CDEK_CLIENT_SECRET

logger = logging.getLogger(__name__)


async def _get_cdek_token() -> str:
    """Получение access_token через OAuth2 (client_credentials)."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{CDEK_API_URL}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CDEK_CLIENT_ID,
                "client_secret": CDEK_CLIENT_SECRET,
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token", "")
            else:
                logger.error("СДЭК авторизация: HTTP %s — %s", resp.status, await resp.text())
                return ""


async def create_cdek_draft(
    fio: str,
    phone: str,
    city: str,
    pvz_address: str,
    order_comment: str = "",
) -> str:
    """
    Создаёт черновик заявки СДЭК.
    Возвращает трек-номер (в MVP — рандомный 9-значный ID).
    """
    # --- MVP: возвращаем рандомный трек-номер ---
    fake_track = "".join(random.choices(string.digits, k=9))
    logger.info("Черновик СДЭК (stub): fio=%s city=%s track=%s", fio, city, fake_track)

    # --- PROD: раскомментируйте и подставьте реальные поля ---
    # token = await _get_cdek_token()
    # if not token:
    #     return "ERR_AUTH"
    # payload = {
    #     "type": 2,  # интернет-магазин
    #     "comment": order_comment,
    #     "delivery_recipient_cost": {"value": 0},
    #     "recipient": {
    #         "name": fio,
    #         "phones": [{"number": phone}],
    #     },
    #     "to_location": {"address": f"{city}, {pvz_address}"},
    #     "packages": [{"number": "1", "weight": 500, "length": 30, "width": 20, "height": 5}],
    #     "services": [{"code": "DELIV_RECEIPT"}],
    # }
    # async with aiohttp.ClientSession() as session:
    #     async with session.post(
    #         f"{CDEK_API_URL}/orders",
    #         json=payload,
    #         headers={"Authorization": f"Bearer {token}"},
    #     ) as resp:
    #         data = await resp.json()
    #         if resp.status == 202:
    #             entity = data.get("entity", {})
    #             return entity.get("uuid", fake_track)
    #         else:
    #             logger.error(f"СДЭК создание заказа: {resp.status} — {data}")
    #             return "ERR_CREATE"

    return fake_track
