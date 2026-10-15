"""Конфигурация бота. Всё читается из переменных окружения / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _parse_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            # Нечисловое значение в списке id — пропускаем, но не падаем.
            continue
    return ids


@dataclass
class Signature:
    prefix: str
    tg_word: str
    tg_url: str
    max_word: str
    max_url: str
    separator: str


@dataclass
class Config:
    telegram_token: str
    telegram_channel_id: str
    allowed_user_ids: set[int]
    signature: Signature
    max_token: str
    max_chat_id: str
    max_api_base: str

    @property
    def max_enabled(self) -> bool:
        return bool(self.max_token and self.max_chat_id)

    def missing_required(self) -> list[str]:
        """Какие обязательные для Telegram поля не заданы."""
        missing = []
        if not self.telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_channel_id:
            missing.append("TELEGRAM_CHANNEL_ID")
        return missing


def load_config() -> Config:
    return Config(
        telegram_token=_get("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_get("TELEGRAM_CHANNEL_ID"),
        allowed_user_ids=_parse_ids(_get("ALLOWED_USER_IDS")),
        signature=Signature(
            prefix=_get("SIGNATURE_PREFIX", "Прикамские Витязи"),
            tg_word=_get("SIGNATURE_TG_WORD", "тг"),
            tg_url=_get("SIGNATURE_TG_URL"),
            max_word=_get("SIGNATURE_MAX_WORD", "макс"),
            max_url=_get("SIGNATURE_MAX_URL"),
            separator=_get("SIGNATURE_SEPARATOR", "/"),
        ),
        max_token=_get("MAX_BOT_TOKEN"),
        max_chat_id=_get("MAX_CHAT_ID"),
        max_api_base=_get("MAX_API_BASE", "https://botapi.max.ru"),
    )
