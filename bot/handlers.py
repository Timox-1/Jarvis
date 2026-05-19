import os
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from tools.memory import get_or_create_user, is_user_allowed, save_message, get_history, clear_history
from tools.files import get_file_text
from bot.agent import run_agent

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


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

    response = await run_agent(user_id, text, history, bot=context.bot)

    save_message(user_id, "assistant", response)
    await update.message.reply_text(response)


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

    response = await run_agent(user_id, user_message, history, bot=context.bot)
    save_message(user_id, "assistant", response)
    await update.message.reply_text(response)

    os.remove(file_path)


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
    await update.message.reply_text(response)
    os.remove(file_path)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я твой личный ИИ-ассистент.\n\n"
        "📋 Задачи и планирование:\n"
        "• «Запиши задачу: ...»\n"
        "• «Что у меня сегодня?»\n"
        "• «Напомни завтра в 10...»\n\n"
        "👥 Контакты и рассылки:\n"
        "• «Добавь контакт: Иван, +7...»\n"
        "• «Разошли клиентам: ...»\n\n"
        "🌐 Действия в интернете:\n"
        "• «Запиши меня к врачу»\n"
        "• «Заполни форму на сайте»\n\n"
        "📄 Файлы и фото — просто отправь\n\n"
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

    # Also close browser session
    from tools.browser import browser_close
    await browser_close()

    await update.message.reply_text(f"История очищена ({count} сообщений удалено). Браузер сброшен. Начинаем с чистого листа!")
