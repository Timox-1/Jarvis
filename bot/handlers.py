import os
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from tools.memory import get_or_create_user, is_user_allowed, save_message, get_history, clear_history
from tools.files import get_file_text
from bot.agent import run_agent

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


async def _safe_reply(message, text: str) -> None:
    """Reply with Markdown, fallback to plain text if parsing fails."""
    try:
        await message.reply_text(text, parse_mode="Markdown")
    except Exception:
        await message.reply_text(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт. Обратитесь к администратору.")
        return

    user_id = get_or_create_user(user.id, user.full_name)
    text = update.message.text or ""

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    history = get_history(user_id)
    save_message(user_id, "user", text)

    error_response = None
    try:
        response = await run_agent(user_id, text, history, bot=context.bot)
    except Exception as e:
        print(f"[agent error] user={user_id}: {e}")
        error_response = "Произошла ошибка при обработке запроса. Попробуй ещё раз."
        response = error_response

    if not error_response:
        save_message(user_id, "assistant", response)

    await _safe_reply(update.message, response)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт.")
        return

    user_id = get_or_create_user(user.id, user.full_name)
    doc = update.message.document
    caption = update.message.caption or "Обработай этот файл"

    file = await context.bot.get_file(doc.file_id)
    file_path = DOWNLOADS_DIR / doc.file_name
    await file.download_to_drive(file_path)

    file_info = get_file_text(str(file_path))
    if file_info["status"] == "error":
        await update.message.reply_text(f"Не могу прочитать файл: {file_info['error']}")
        return

    if file_info["type"] == "pdf":
        user_message = f"{caption}\n\n[Содержимое PDF '{doc.file_name}']:\n{file_info['text']}"
    else:
        user_message = caption

    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    history = get_history(user_id)
    save_message(user_id, "user", user_message)

    error_response = None
    try:
        response = await run_agent(user_id, user_message, history, bot=context.bot)
    except Exception as e:
        print(f"[document agent error] user={user_id}: {e}")
        error_response = "Произошла ошибка при обработке файла. Попробуй ещё раз."
        response = error_response
    finally:
        if file_path.exists():
            os.remove(file_path)

    if not error_response:
        save_message(user_id, "assistant", response)

    await _safe_reply(update.message, response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт.")
        return

    user_id = get_or_create_user(user.id, user.full_name)
    caption = update.message.caption or "Что на этом фото?"

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = DOWNLOADS_DIR / f"{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    file_info = get_file_text(str(file_path))
    if file_info["status"] == "error":
        await update.message.reply_text(f"Ошибка: {file_info['error']}")
        return

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    from openai import AsyncOpenAI
    from config import BOTHUB_API_KEY, BOTHUB_BASE_URL, GPT_MODEL
    from system_prompt import get_system_prompt
    from tools.memory import read_memory

    memory = read_memory(user_id)
    vision_client = AsyncOpenAI(api_key=BOTHUB_API_KEY, base_url=BOTHUB_BASE_URL)
    response_obj = await vision_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": get_system_prompt(memory)},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": caption},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{file_info['base64']}"
                        },
                    },
                ],
            },
        ],
        max_tokens=1000,
    )
    response = response_obj.choices[0].message.content or ""

    history = get_history(user_id)
    save_message(user_id, "user", f"{caption} [фото]")
    save_message(user_id, "assistant", response)
    await _safe_reply(update.message, response)
    os.remove(file_path)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт.")
        return

    user_id = get_or_create_user(user.id, user.full_name)
    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = DOWNLOADS_DIR / f"{voice.file_id}.ogg"
    await file.download_to_drive(file_path)

    try:
        from openai import AsyncOpenAI
        from config import BOTHUB_API_KEY, BOTHUB_BASE_URL

        client = AsyncOpenAI(api_key=BOTHUB_API_KEY, base_url=BOTHUB_BASE_URL)
        with open(file_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru",
            )

        text = transcription.text.strip()
        if not text:
            await update.message.reply_text("Не удалось распознать голос. Попробуй ещё раз.")
            return

        await update.message.reply_text(f"🎤 {text}")

        history = get_history(user_id)
        save_message(user_id, "user", text)
        response = await run_agent(user_id, text, history, bot=context.bot)
        save_message(user_id, "assistant", response)
        await _safe_reply(update.message, response)

    finally:
        if file_path.exists():
            os.remove(file_path)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я твой личный ИИ-ассистент.\n\n"
        "📋 Задачи и планирование:\n"
        "• «Запиши задачу: ...»\n"
        "• «Что у меня сегодня?»\n"
        "• «Напомни завтра в 10...»\n"
        "• «Перенеси задачу на пятницу»\n\n"
        "👥 Контакты и рассылки:\n"
        "• «Добавь контакт: Иван, +7...»\n"
        "• «Добавь Ивана в группу Клиенты»\n"
        "• «Разошли клиентам: ...»\n\n"
        "💰 Финансы:\n"
        "• «Клиент оплатил 50000₽»\n"
        "• «Потратил 3000 на такси»\n"
        "• «Покажи финансовую сводку за месяц»\n\n"
        "📅 Яндекс Календарь:\n"
        "• «Что у меня в календаре на неделе?»\n"
        "• «Запиши встречу на завтра в 15:00»\n\n"
        "🌐 Действия в интернете:\n"
        "• «Запиши меня к врачу»\n"
        "• «Заполни форму на сайте»\n\n"
        "📄 Файлы и фото — просто отправь\n\n"
        "/status — быстрый дашборд\n"
        "/connect_calendar — подключить Яндекс Календарь\n"
        "/clear — очистить историю\n\n"
        "Просто напиши что нужно!"
    )


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт.")
        return

    user_id = get_or_create_user(user.id, user.full_name)
    count = clear_history(user_id)

    from tools.browser import browser_close
    await browser_close()

    await update.message.reply_text(f"История очищена ({count} сообщений удалено). Браузер сброшен. Начинаем с чистого листа!")


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт.")
        return

    user_id = get_or_create_user(user.id, user.full_name)

    from tools.tasks import get_today_summary
    from tools.reminders import list_reminders
    from db.client import get_db

    summary = get_today_summary(user_id)
    reminders = list_reminders(user_id)

    db = get_db()
    cal_connected = bool(
        db.table("user_integrations")
        .select("id")
        .eq("user_id", user_id)
        .eq("provider", "yandex_calendar")
        .execute().data
    )

    lines = ["*Статус Джарвиса*\n"]

    overdue = summary["summary"]["overdue_count"]
    today_count = summary["summary"]["today_count"]
    tomorrow_count = summary["summary"]["tomorrow_count"]

    if overdue:
        lines.append(f"🔴 Просрочено задач: *{overdue}*")
    lines.append(f"📋 Задач на сегодня: *{today_count}*")
    lines.append(f"📅 Задач на завтра: *{tomorrow_count}*")
    lines.append(f"⏰ Активных напоминаний: *{len(reminders)}*")
    cal_status = "подключён ✅" if cal_connected else "не подключён — /connect\\_calendar"
    lines.append(f"📆 Яндекс Календарь: {cal_status}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_connect_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.message.reply_text("Доступ закрыт.")
        return

    from config import YANDEX_CALENDAR_CLIENT_ID
    user_id = get_or_create_user(user.id, user.full_name)

    oauth_url = (
        "https://oauth.yandex.ru/authorize"
        f"?client_id={YANDEX_CALENDAR_CLIENT_ID}"
        "&response_type=code"
        "&scope=calendar:all+login:email+login:info"
        f"&state={user_id}"
        "&force_confirm=yes"
    )

    await update.message.reply_text(
        "📅 Подключение Яндекс Календаря\n\n"
        f"Нажми на ссылку и войди в Яндекс:\n{oauth_url}\n\n"
        "После входа вернись сюда — бот подтвердит подключение."
    )
