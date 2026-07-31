import os
import subprocess
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from openai import AsyncOpenAI
from tools.memory import (
    get_or_create_user,
    is_user_allowed,
    save_message,
    clear_history,
    access_denied_text,
    invite_user,
    link_identity,
    find_user_id_by_telegram,
    VALID_PLANS,
)
from tools.files import get_file_text
from bot.process import process_text
from channels.base import DeliveryContext
from channels.router import get_router
from config import BOTHUB_API_KEY, BOTHUB_BASE_URL, WHISPER_MODEL, ADMIN_TELEGRAM_IDS, ALLOWED_TELEGRAM_IDS

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

ONBOARDING = (
    "Привет! Я Джарвис — личный ИИ-ассистент.\n\n"
    "Умею:\n"
    "• проекты — скажи «создай проект/объект/дело …», кидай инфу, разложу по задачам и тратам\n"
    "• задачи, напоминания, утренний брифинг в 09:00\n"
    "• Яндекс Календарь — /connect_calendar\n"
    "• почту, контакты, заметки, учёт расходов\n"
    "• голос, фото, PDF, браузер\n\n"
    "Просто напиши обычным языком. Голосовые тоже ок.\n\n"
    "/status — сводка дня\n"
    "/connect_calendar — Яндекс Календарь\n"
    "/clear — очистить историю"
)

def _delivery(update: Update) -> DeliveryContext:
    return DeliveryContext(channel="telegram", external_id=str(update.effective_user.id))


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_TELEGRAM_IDS or telegram_id in ALLOWED_TELEGRAM_IDS


async def _safe_reply(message, text: str) -> None:
    """Reply with Markdown, fallback to plain text if parsing fails."""
    try:
        await message.reply_text(text, parse_mode="Markdown")
    except Exception:
        await message.reply_text(text)


async def _deny_if_needed(update: Update) -> bool:
    """Return True if access denied (and reply sent). Still registers inactive user on /start path."""
    user = update.effective_user
    if is_user_allowed("telegram", user.id):
        return False
    await update.message.reply_text(access_denied_text())
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    user_id = get_or_create_user("telegram", user.id, user.full_name)
    text = update.message.text or ""
    response = await process_text(user_id, text, _delivery(update))
    await _safe_reply(update.message, response)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    user_id = get_or_create_user("telegram", user.id, user.full_name)
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

    try:
        response = await process_text(user_id, user_message, _delivery(update))
        await _safe_reply(update.message, response)
    finally:
        if file_path.exists():
            os.remove(file_path)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    user_id = get_or_create_user("telegram", user.id, user.full_name)
    caption = update.message.caption or "Что на этом фото?"

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = DOWNLOADS_DIR / f"{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    file_info = get_file_text(str(file_path))
    if file_info["status"] == "error":
        await update.message.reply_text(f"Ошибка: {file_info['error']}")
        return

    await get_router().send_typing("telegram", str(user.id))

    from config import GPT_MODEL
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

    save_message(user_id, "user", f"{caption} [фото]")
    save_message(user_id, "assistant", response)
    await _safe_reply(update.message, response)
    os.remove(file_path)


def _convert_ogg_to_mp3(ogg_path: Path) -> Path:
    mp3_path = ogg_path.with_suffix(".mp3")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(ogg_path),
            "-ac", "1", "-ar", "16000",
            "-codec:a", "libmp3lame", "-q:a", "4",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not mp3_path.exists():
        raise RuntimeError(result.stderr.strip() or "ffmpeg conversion failed")
    return mp3_path


async def _transcribe_audio(mp3_path: Path) -> str:
    fallbacks = (
        ("https://openai.bothub.chat/v1", "whisper-1"),
        (BOTHUB_BASE_URL, "assembly-ai-best"),
        (BOTHUB_BASE_URL, WHISPER_MODEL),
    )
    errors = []

    for base_url, model in fallbacks:
        client = AsyncOpenAI(api_key=BOTHUB_API_KEY, base_url=base_url)
        try:
            with open(mp3_path, "rb") as audio_file:
                transcription = await client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language="ru",
                )
            text = (transcription.text or "").strip()
            if text:
                print(f"[voice transcribe ok] model={model} base={base_url}")
                return text
            errors.append(f"{model}@{base_url}: empty transcript")
        except Exception as e:
            errors.append(f"{model}@{base_url}: {e}")

    raise RuntimeError("; ".join(errors))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    user_id = get_or_create_user("telegram", user.id, user.full_name)
    await get_router().send_typing("telegram", str(user.id))

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = DOWNLOADS_DIR / f"{voice.file_id}.ogg"
    mp3_path = None

    try:
        await file.download_to_drive(file_path)
        mp3_path = _convert_ogg_to_mp3(file_path)
        text = await _transcribe_audio(mp3_path)
        if not text:
            await update.message.reply_text("Не удалось распознать голос. Попробуй ещё раз.")
            return

        await update.message.reply_text(f"🎤 {text}")
        response = await process_text(user_id, text, _delivery(update))
        await _safe_reply(update.message, response)

    except Exception as e:
        print(f"[voice error] user={user_id}: {e}")
        await update.message.reply_text(
            "Не удалось обработать голосовое. Попробуй ещё раз или напиши текстом."
        )
    finally:
        for path in (file_path, mp3_path):
            if path and path.exists():
                os.remove(path)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    get_or_create_user("telegram", user.id, user.full_name)
    if not is_user_allowed("telegram", user.id):
        await update.message.reply_text(access_denied_text())
        return
    await update.message.reply_text(ONBOARDING)


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    user_id = get_or_create_user("telegram", user.id, user.full_name)
    count = clear_history(user_id)

    from tools.browser import browser_close
    await browser_close()

    await update.message.reply_text(
        f"История очищена ({count} сообщений удалено). Браузер сброшен. Начинаем с чистого листа!"
    )


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    user_id = get_or_create_user("telegram", user.id, user.full_name)

    from tools.tasks import get_today_summary
    from tools.reminders import list_reminders
    from tools.memory import get_user_profile
    from db.client import get_db

    summary = get_today_summary(user_id)
    reminders = list_reminders(user_id)
    profile = get_user_profile(user_id)

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
    if profile:
        plan = profile.get("plan") or "—"
        paid = profile.get("paid_until") or "—"
        lines.append(f"🎫 Тариф: *{plan}* (до {paid})" if paid != "—" else f"🎫 Тариф: *{plan}*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_connect_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if await _deny_if_needed(update):
        return

    from config import YANDEX_CALENDAR_CLIENT_ID
    user_id = get_or_create_user("telegram", user.id, user.full_name)

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


async def handle_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /invite <telegram_id> [plan] [paid_until=YYYY-MM-DD]"""
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Команда только для администратора.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Использование:\n"
            "/invite <telegram_id> [plan] [YYYY-MM-DD]\n"
            f"Планы: {', '.join(VALID_PLANS)}\n"
            "Пример: /invite 123456789 trial\n"
            "Пример: /invite 123456789 base 2026-09-01"
        )
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("telegram_id должен быть числом.")
        return

    plan = args[1] if len(args) > 1 else "trial"
    paid_until = args[2] if len(args) > 2 else None

    try:
        result = invite_user("telegram", telegram_id, plan=plan, paid_until=paid_until)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return
    except Exception as e:
        await update.message.reply_text(f"Ошибка инвайта: {e}")
        return

    action = "создан" if result["created"] else "активирован"
    await update.message.reply_text(
        f"✅ Пользователь {action}\n"
        f"TG: {result['external_id']}\n"
        f"plan: {result['plan']}\n"
        f"paid_until: {result['paid_until'] or '—'}\n"
        f"user_id: {result['user_id']}"
    )


async def handle_invite_vk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /invite_vk <vk_id> [plan] [paid_until=YYYY-MM-DD]"""
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Команда только для администратора.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Использование:\n"
            "/invite_vk <vk_id> [plan] [YYYY-MM-DD]\n"
            "Пример: /invite_vk 12345678 trial"
        )
        return

    try:
        vk_id = int(args[0])
    except ValueError:
        await update.message.reply_text("vk_id должен быть числом.")
        return

    plan = args[1] if len(args) > 1 else "trial"
    paid_until = args[2] if len(args) > 2 else None

    try:
        result = invite_user("vk", vk_id, plan=plan, paid_until=paid_until)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return
    except Exception as e:
        await update.message.reply_text(f"Ошибка инвайта: {e}")
        return

    action = "создан" if result["created"] else "активирован"
    await update.message.reply_text(
        f"✅ VK-пользователь {action}\n"
        f"VK: {result['external_id']}\n"
        f"plan: {result['plan']}\n"
        f"paid_until: {result['paid_until'] or '—'}\n"
        f"user_id: {result['user_id']}"
    )


async def handle_link_vk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /link_vk <telegram_id> <vk_id> — same person, both channels."""
    user = update.effective_user
    if not _is_admin(user.id):
        await update.message.reply_text("Команда только для администратора.")
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Использование: /link_vk <telegram_id> <vk_id>")
        return

    try:
        telegram_id = int(args[0])
        vk_id = int(args[1])
    except ValueError:
        await update.message.reply_text("Оба ID должны быть числами.")
        return

    user_id = find_user_id_by_telegram(telegram_id)
    if not user_id:
        await update.message.reply_text(
            f"Сначала /invite {telegram_id}, потом /link_vk."
        )
        return

    try:
        msg = link_identity(user_id, "vk", vk_id)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    await update.message.reply_text(f"✅ {msg}")
