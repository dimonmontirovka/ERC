"""Сборка поста с подписью.

Подпись — это последняя строка вида:

    Прикамские Витязи тг/макс

где «тг» и «макс» — гиперссылки. Строка отделяется от текста поста
пустой строкой ("через строку").

Для Telegram подпись добавляется через entities (а не через разметку),
чтобы собственное форматирование поста друга (жирный, курсив, его
ссылки, эмодзи) сохранялось без искажений и экранирования.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from telegram import MessageEntity

from config import Signature

# Пустая строка между текстом поста и подписью.
SEPARATOR = "\n\n"


def _u16_len(text: str) -> int:
    """Длина строки в кодовых единицах UTF-16.

    Telegram задаёт offset/length entities именно в единицах UTF-16,
    поэтому смещения считаем так, а не через len().
    """
    return len(text.encode("utf-16-le")) // 2


@dataclass
class BuiltPost:
    text: str
    entities: list[MessageEntity]


def build_signature_text(sig: Signature) -> str:
    """Голый текст подписи без ведущего разделителя: 'Прикамские Витязи тг/макс'."""
    prefix = f"{sig.prefix} " if sig.prefix else ""
    return f"{prefix}{sig.tg_word}{sig.separator}{sig.max_word}"


def build_telegram_post(
    text: str,
    entities: list[MessageEntity] | tuple[MessageEntity, ...] | None,
    sig: Signature,
) -> BuiltPost:
    """Склеивает текст поста с подписью и возвращает текст + entities.

    `text` и `entities` — это message.text и message.entities исходного
    сообщения от пользователя. Их offset'ы отсчитываются от начала текста,
    поэтому при дописывании подписи в конец они остаются валидными.
    """
    entities = list(entities or [])

    prefix = f"{sig.prefix} " if sig.prefix else ""
    new_text = f"{text}{SEPARATOR}{prefix}{sig.tg_word}{sig.separator}{sig.max_word}"

    # Смещения слов-ссылок в единицах UTF-16.
    before_tg = _u16_len(f"{text}{SEPARATOR}{prefix}")
    tg_len = _u16_len(sig.tg_word)

    before_max = _u16_len(f"{text}{SEPARATOR}{prefix}{sig.tg_word}{sig.separator}")
    max_len = _u16_len(sig.max_word)

    new_entities = list(entities)
    if sig.tg_url:
        new_entities.append(
            MessageEntity(
                type=MessageEntity.TEXT_LINK,
                offset=before_tg,
                length=tg_len,
                url=sig.tg_url,
            )
        )
    if sig.max_url:
        new_entities.append(
            MessageEntity(
                type=MessageEntity.TEXT_LINK,
                offset=before_max,
                length=max_len,
                url=sig.max_url,
            )
        )

    return BuiltPost(text=new_text, entities=new_entities)


def build_max_html(text: str, sig: Signature) -> str:
    """HTML-вариант поста для МАКСа (его Bot API принимает format=html).

    Текст поста экранируется; ссылки добавляются как <a href>.
    Форматирование исходного поста здесь не переносится (МАКС получает
    только текст), но ссылки подписи ставятся корректно.
    """
    prefix = f"{html.escape(sig.prefix)} " if sig.prefix else ""
    tg = (
        f'<a href="{html.escape(sig.tg_url, quote=True)}">{html.escape(sig.tg_word)}</a>'
        if sig.tg_url
        else html.escape(sig.tg_word)
    )
    mx = (
        f'<a href="{html.escape(sig.max_url, quote=True)}">{html.escape(sig.max_word)}</a>'
        if sig.max_url
        else html.escape(sig.max_word)
    )
    sep = html.escape(sig.separator)
    return f"{html.escape(text)}{SEPARATOR}{prefix}{tg}{sep}{mx}"
