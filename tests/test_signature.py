"""Проверка корректности сборки подписи и смещений ссылок."""
from telegram import MessageEntity

from config import Signature
from signature import build_max_html, build_telegram_post


SIG = Signature(
    prefix="Прикамские Витязи",
    tg_word="тг",
    tg_url="https://t.me/vityazi",
    max_word="макс",
    max_url="https://max.ru/vityazi",
    separator="/",
)


def _slice_u16(text: str, offset: int, length: int) -> str:
    """Вырезать подстроку по UTF-16 offset/length, как это делает Telegram."""
    data = text.encode("utf-16-le")
    return data[offset * 2 : (offset + length) * 2].decode("utf-16-le")


def test_plain_post_links_point_to_right_words():
    post = "Сегодня игра! 🏒"
    built = build_telegram_post(post, [], SIG)

    assert built.text.endswith("Прикамские Витязи тг/макс")
    assert "\n\n" in built.text

    links = [e for e in built.entities if e.type == MessageEntity.TEXT_LINK]
    assert len(links) == 2

    tg = next(e for e in links if e.url == SIG.tg_url)
    mx = next(e for e in links if e.url == SIG.max_url)

    # Ссылки должны покрывать ровно слова «тг» и «макс».
    assert _slice_u16(built.text, tg.offset, tg.length) == "тг"
    assert _slice_u16(built.text, mx.offset, mx.length) == "макс"


def test_existing_entities_preserved_with_emoji_and_formatting():
    # Пост с эмодзи (суррогатная пара в UTF-16) и жирным словом.
    post = "🏒 Важно: победа"
    # «Важно» выделено жирным — offset в UTF-16: 🏒=2, пробел=1 → 3.
    bold = MessageEntity(type=MessageEntity.BOLD, offset=3, length=5)
    built = build_telegram_post(post, [bold], SIG)

    # Исходный bold не тронут.
    assert bold in built.entities
    assert _slice_u16(built.text, bold.offset, bold.length) == "Важно"

    # И ссылки по-прежнему попадают на нужные слова несмотря на эмодзи.
    links = [e for e in built.entities if e.type == MessageEntity.TEXT_LINK]
    tg = next(e for e in links if e.url == SIG.tg_url)
    mx = next(e for e in links if e.url == SIG.max_url)
    assert _slice_u16(built.text, tg.offset, tg.length) == "тг"
    assert _slice_u16(built.text, mx.offset, mx.length) == "макс"


def test_max_html_escapes_and_links():
    post = "Счёт 5<3 & всё"
    out = build_max_html(post, SIG)
    assert "5&lt;3 &amp; всё" in out
    assert '<a href="https://t.me/vityazi">тг</a>' in out
    assert '<a href="https://max.ru/vityazi">макс</a>' in out


if __name__ == "__main__":
    test_plain_post_links_point_to_right_words()
    test_existing_entities_preserved_with_emoji_and_formatting()
    test_max_html_escapes_and_links()
    print("OK — все проверки прошли")
