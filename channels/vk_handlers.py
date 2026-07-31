"""VK message handlers — text, voice, photo parity with Telegram."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
from vkbottle.bot import Message

from channels.base import DeliveryContext
from channels.vk import VKAdapter
from bot.process import process_text
from bot.admin_notify import notify_access_denied
from tools.memory import (
    access_denied_text,
    get_or_create_user,
    is_user_allowed,
    save_message,
    clear_history,
)


async def _vk_deny(message, peer_id: int, *, via: str = "message") -> None:
    await message.answer(access_denied_text())
    await notify_access_denied(channel="vk", external_id=peer_id, via=via)


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

async def handle_vk_message(message: Message, adapter: VKAdapter) -> None:
    peer_id = message.from_id
    if peer_id is None or peer_id < 0:
        return  # ignore group/chat system events

    external_id = str(peer_id)
    name = f"VK {peer_id}"
    try:
        users = await adapter.api.users.get(user_ids=[peer_id])
        if users:
            name = f"{users[0].first_name} {users[0].last_name}".strip()
    except Exception:
        pass

    text = (message.text or "").strip()
    delivery = DeliveryContext(channel="vk", external_id=external_id)

    # Commands
    if text.startswith("/start") or text.lower() in ("начать", "start"):
        user_id = get_or_create_user("vk", peer_id, name)
        if not is_user_allowed("vk", peer_id):
            await _vk_deny(message, peer_id, via="start")
            return
        await message.answer(ONBOARDING)
        return

    if text.startswith("/clear"):
        if not is_user_allowed("vk", peer_id):
            await _vk_deny(message, peer_id)
            return
        user_id = get_or_create_user("vk", peer_id, name)
        count = clear_history(user_id)
        await message.answer(f"История очищена ({count} сообщений).")
        return

    if text.startswith("/status"):
        if not is_user_allowed("vk", peer_id):
            await _vk_deny(message, peer_id)
            return
        user_id = get_or_create_user("vk", peer_id, name)
        from tools.tasks import get_today_summary
        from tools.reminders import list_reminders
        summary = get_today_summary(user_id)
        reminders = list_reminders(user_id)
        lines = [
            "Статус Джарвиса\n",
            f"Просрочено: {summary['summary']['overdue_count']}",
            f"Сегодня: {summary['summary']['today_count']}",
            f"Напоминаний: {len(reminders)}",
        ]
        await message.answer("\n".join(lines))
        return

    if not is_user_allowed("vk", peer_id):
        get_or_create_user("vk", peer_id, name)
        await message.answer(access_denied_text())
        return

    user_id = get_or_create_user("vk", peer_id, name)

    # Voice / audio message
    audio_url = _extract_audio_url(message)
    if audio_url:
        transcript = await _transcribe_vk_audio(audio_url)
        if not transcript:
            await message.answer("Не удалось распознать голос. Напиши текстом.")
            return
        await message.answer(f"🎤 {transcript}")
        response = await process_text(user_id, transcript, delivery)
        await message.answer(response)
        return

    # Photo
    photo_url = _extract_photo_url(message)
    if photo_url:
        caption = text or "Что на этом фото?"
        await _handle_vk_photo(user_id, photo_url, caption, message)
        return

    if not text:
        await message.answer("Пришли текст, голос или фото.")
        return

    response = await process_text(user_id, text, delivery)
    await message.answer(response)


def _extract_audio_url(message: Message) -> str | None:
    for att in message.attachments or []:
        audio = getattr(att, "audio_message", None)
        if audio is None and hasattr(att, "type") and str(att.type) == "audio_message":
            audio = getattr(att, "audio_message", None)
        if audio is not None:
            link = getattr(audio, "link_mp3", None) or getattr(audio, "link_ogg", None)
            if link:
                return link
            # dict-like fallback
            if isinstance(audio, dict):
                return audio.get("link_mp3") or audio.get("link_ogg")
    return None


def _extract_photo_url(message: Message) -> str | None:
    for att in message.attachments or []:
        photo = getattr(att, "photo", None)
        if photo is None:
            continue
        sizes = getattr(photo, "sizes", None) or []
        if not sizes and isinstance(photo, dict):
            sizes = photo.get("sizes") or []
        if not sizes:
            continue
        # pick largest
        best = max(sizes, key=lambda s: getattr(s, "width", 0) * getattr(s, "height", 0)
                   if not isinstance(s, dict) else s.get("width", 0) * s.get("height", 0))
        url = getattr(best, "url", None) if not isinstance(best, dict) else best.get("url")
        if url:
            return url
    return None


async def _transcribe_vk_audio(url: str) -> str:
    from openai import AsyncOpenAI
    from config import BOTHUB_API_KEY, BOTHUB_BASE_URL, WHISPER_MODEL
    from bot.handlers import _convert_ogg_to_mp3, _transcribe_audio

    file_path = DOWNLOADS_DIR / f"vk_voice_{abs(hash(url)) % 10_000_000}.mp3"
    mp3_path = None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            file_path.write_bytes(resp.content)

        # If ogg, convert; if already mp3, use as-is
        if url.endswith(".ogg") or resp.content[:4] == b"OggS":
            ogg_path = file_path.with_suffix(".ogg")
            file_path.rename(ogg_path)
            mp3_path = _convert_ogg_to_mp3(ogg_path)
            if ogg_path.exists():
                os.remove(ogg_path)
            return await _transcribe_audio(mp3_path)

        # treat as mp3
        client = AsyncOpenAI(api_key=BOTHUB_API_KEY, base_url=BOTHUB_BASE_URL)
        with open(file_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
                language="ru",
            )
        return (transcription.text or "").strip()
    except Exception as e:
        print(f"[vk voice] {e}")
        # fallback through shared pipeline if file looks like ogg
        try:
            if file_path.exists():
                ogg = file_path.with_suffix(".ogg")
                if not ogg.exists():
                    file_path.rename(ogg)
                mp3_path = _convert_ogg_to_mp3(ogg)
                return await _transcribe_audio(mp3_path)
        except Exception as e2:
            print(f"[vk voice fallback] {e2}")
        return ""
    finally:
        for p in (file_path, mp3_path):
            if p and Path(p).exists():
                try:
                    os.remove(p)
                except OSError:
                    pass


async def _handle_vk_photo(user_id: str, photo_url: str, caption: str, message: Message) -> None:
    from openai import AsyncOpenAI
    from config import BOTHUB_API_KEY, BOTHUB_BASE_URL, GPT_MODEL
    from system_prompt import get_system_prompt
    from tools.memory import read_memory

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(photo_url)
        resp.raise_for_status()
        raw = resp.content

    b64 = base64.b64encode(raw).decode("ascii")
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
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
        max_tokens=1000,
    )
    response = response_obj.choices[0].message.content or ""
    save_message(user_id, "user", f"{caption} [фото]")
    save_message(user_id, "assistant", response)
    await message.answer(response)
