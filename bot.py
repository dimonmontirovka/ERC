"""Telegram-бот «пульт публикации».

Друг присылает боту текст поста → бот показывает превью с уже
добавленной последней строкой-подписью («Прикамские Витязи тг/макс»,
где «тг» и «макс» — ссылки) и кнопки выбора площадки
(Telegram / МАКС / Выбрать всё) + «Опубликовать». По нажатию публикует
туда, где выбрано.
"""
from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, load_config
from publishers.max_publisher import MaxPublishError, publish_to_max
from signature import build_max_html, build_telegram_post

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("vityazi-bot")

# Ключи в context.user_data
K_TEXT = "draft_text"
K_ENTITIES = "draft_entities"
K_DEST = "draft_dest"


def _is_allowed(cfg: Config, user_id: int | None) -> bool:
    return user_id is not None and user_id in cfg.allowed_user_ids


def _keyboard(dest: set[str], max_enabled: bool) -> InlineKeyboardMarkup:
    tg_mark = "✅" if "tg" in dest else "⬜️"
    max_mark = "✅" if "max" in dest else "⬜️"
    max_label = f"{max_mark} МАКС" if max_enabled else "🚧 МАКС (скоро)"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"{tg_mark} Telegram", callback_data="toggle_tg"),
                InlineKeyboardButton(max_label, callback_data="toggle_max"),
            ],
            [InlineKeyboardButton("Выбрать всё", callback_data="set_all")],
            [
                InlineKeyboardButton("📢 Опубликовать", callback_data="publish"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
            ],
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    uid = user.id if user else None

    if not _is_allowed(cfg, uid):
        await update.message.reply_text(
            "Привет! Этот бот — личный пульт публикации.\n\n"
            f"Твой Telegram ID: `{uid}`\n\n"
            "Чтобы получить доступ, добавь этот ID в переменную "
            "`ALLOWED_USER_IDS` в настройках бота и перезапусти его.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Пришли мне текст поста — я добавлю в конце строку "
        "«Прикамские Витязи тг/макс» со ссылками и покажу превью. "
        "Дальше выберешь, куда опубликовать, и нажмёшь «Опубликовать».\n\n"
        "Форматирование твоего поста (жирный, ссылки, эмодзи) сохраняется."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    uid = user.id if user else None

    if not _is_allowed(cfg, uid):
        await update.message.reply_text(
            f"Нет доступа. Твой ID: `{uid}`. Попроси добавить его в ALLOWED_USER_IDS.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    msg = update.message
    text = msg.text or ""
    if not text.strip():
        await msg.reply_text("Пришли текст поста сообщением.")
        return

    built = build_telegram_post(text, msg.entities, cfg.signature)

    # Сохраняем черновик и сбрасываем выбор площадок.
    context.user_data[K_TEXT] = text
    context.user_data[K_ENTITIES] = list(msg.entities or [])
    context.user_data[K_DEST] = set()

    await msg.reply_text(
        built.text,
        entities=built.entities,
        reply_markup=_keyboard(context.user_data[K_DEST], cfg.max_enabled),
        disable_web_page_preview=True,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    query = update.callback_query
    user = update.effective_user
    uid = user.id if user else None

    if not _is_allowed(cfg, uid):
        await query.answer("Нет доступа.", show_alert=True)
        return

    data = query.data or ""
    dest: set[str] = context.user_data.get(K_DEST)
    if dest is None:
        await query.answer("Черновик не найден, пришли текст заново.", show_alert=True)
        return

    if data == "toggle_tg":
        dest.symmetric_difference_update({"tg"})
        await query.answer()
        await query.edit_message_reply_markup(_keyboard(dest, cfg.max_enabled))
        return

    if data == "toggle_max":
        if not cfg.max_enabled:
            await query.answer(
                "МАКС ещё не подключён. Нужен токен бота МАКС — тогда кнопка заработает.",
                show_alert=True,
            )
            return
        dest.symmetric_difference_update({"max"})
        await query.answer()
        await query.edit_message_reply_markup(_keyboard(dest, cfg.max_enabled))
        return

    if data == "set_all":
        dest.clear()
        dest.add("tg")
        if cfg.max_enabled:
            dest.add("max")
        await query.answer("Выбраны все площадки.")
        await query.edit_message_reply_markup(_keyboard(dest, cfg.max_enabled))
        return

    if data == "cancel":
        context.user_data.pop(K_TEXT, None)
        context.user_data.pop(K_ENTITIES, None)
        context.user_data.pop(K_DEST, None)
        await query.answer("Отменено.")
        await query.edit_message_reply_markup(None)
        return

    if data == "publish":
        if not dest:
            await query.answer("Сначала выбери хотя бы одну площадку.", show_alert=True)
            return
        await _do_publish(update, context, cfg, dest)
        return

    await query.answer()


async def _do_publish(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cfg: Config,
    dest: set[str],
) -> None:
    query = update.callback_query
    await query.answer("Публикую…")

    text = context.user_data.get(K_TEXT, "")
    entities = context.user_data.get(K_ENTITIES, [])

    results: list[str] = []

    if "tg" in dest:
        try:
            built = build_telegram_post(text, entities, cfg.signature)
            await context.bot.send_message(
                chat_id=cfg.telegram_channel_id,
                text=built.text,
                entities=built.entities,
                disable_web_page_preview=True,
            )
            results.append("✅ Telegram — опубликовано")
        except TelegramError as exc:
            logger.exception("Ошибка публикации в Telegram")
            results.append(f"❌ Telegram — ошибка: {exc}")

    if "max" in dest:
        try:
            html_text = build_max_html(text, cfg.signature)
            await publish_to_max(cfg, html_text)
            results.append("✅ МАКС — опубликовано")
        except MaxPublishError as exc:
            results.append(f"❌ МАКС — {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка публикации в МАКС")
            results.append(f"❌ МАКС — ошибка: {exc}")

    # Убираем кнопки у превью и пишем итог.
    try:
        await query.edit_message_reply_markup(None)
    except TelegramError:
        pass

    await query.message.reply_text("Готово:\n" + "\n".join(results))

    # Чистим черновик.
    context.user_data.pop(K_TEXT, None)
    context.user_data.pop(K_ENTITIES, None)
    context.user_data.pop(K_DEST, None)


def build_application(cfg: Config) -> Application:
    app = Application.builder().token(cfg.telegram_token).build()
    app.bot_data["cfg"] = cfg
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    cfg = load_config()
    missing = cfg.missing_required()
    if missing:
        raise SystemExit(
            "Не заданы обязательные переменные: "
            + ", ".join(missing)
            + ".\nСкопируй .env.example в .env и заполни его."
        )
    if not cfg.allowed_user_ids:
        logger.warning(
            "ALLOWED_USER_IDS пуст — пользоваться ботом никто не сможет. "
            "Напиши боту /start, узнай свой ID и добавь его."
        )

    app = build_application(cfg)
    logger.info("Бот запущен. Публикация в канал: %s", cfg.telegram_channel_id)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
