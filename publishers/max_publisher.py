"""Публикация в МАКС через его Bot API.

Код написан «под ключ» по известной форме Bot API МАКС
(botapi.max.ru, наследник TamTam Bot API): отправка сообщения —
POST {base}/messages?access_token=...&chat_id=... с телом
{"text": ..., "format": "html"}.

ВНИМАНИЕ: пока нет рабочего токена, реальные вызовы не проверены.
Когда токен появится — задать MAX_BOT_TOKEN и MAX_CHAT_ID в .env и
сверить имена полей с актуальной документацией botapi.max.ru.
Пока токена нет, publish_to_max() не вызывается (бот сообщает, что
площадка не подключена) — см. config.max_enabled.
"""
from __future__ import annotations

import httpx

from config import Config


class MaxPublishError(Exception):
    pass


async def publish_to_max(cfg: Config, html_text: str) -> None:
    if not cfg.max_enabled:
        raise MaxPublishError("МАКС не настроен: задай MAX_BOT_TOKEN и MAX_CHAT_ID.")

    url = f"{cfg.max_api_base.rstrip('/')}/messages"
    params = {"access_token": cfg.max_token, "chat_id": cfg.max_chat_id}
    payload = {"text": html_text, "format": "html", "notify": True}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, params=params, json=payload)
    except httpx.HTTPError as exc:
        raise MaxPublishError(f"Сетевая ошибка при обращении к МАКС: {exc}") from exc

    if resp.status_code >= 400:
        raise MaxPublishError(
            f"МАКС вернул {resp.status_code}: {resp.text[:500]}"
        )
