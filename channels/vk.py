"""VK community bot channel adapter + Long Poll runner."""

from __future__ import annotations

import random
from io import BytesIO

import httpx

from channels.base import ChannelAdapter


def _rand_id() -> int:
    return random.randint(1, 2**31 - 1)


class VKAdapter(ChannelAdapter):
    channel = "vk"

    def __init__(self, api) -> None:
        """api: vkbottle.api.API instance."""
        self.api = api

    async def send_text(
        self,
        external_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        plain = text.replace("\\_", "_") if parse_mode else text
        await self.api.messages.send(
            user_id=int(external_id),
            message=plain,
            random_id=_rand_id(),
        )

    async def send_photo(
        self,
        external_id: str,
        photo: bytes,
        caption: str | None = None,
    ) -> None:
        upload = await self.api.photos.get_messages_upload_server(peer_id=int(external_id))
        upload_url = upload["upload_url"] if isinstance(upload, dict) else upload.upload_url

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                upload_url,
                files={"photo": ("screenshot.png", BytesIO(photo), "image/png")},
            )
            resp.raise_for_status()
            payload = resp.json()

        saved = await self.api.photos.save_messages_photo(
            photo=payload["photo"],
            server=payload["server"],
            hash=payload["hash"],
        )
        photo_obj = saved[0]
        owner_id = photo_obj["owner_id"] if isinstance(photo_obj, dict) else photo_obj.owner_id
        photo_id = photo_obj["id"] if isinstance(photo_obj, dict) else photo_obj.id
        attachment = f"photo{owner_id}_{photo_id}"
        await self.api.messages.send(
            user_id=int(external_id),
            message=caption or "",
            attachment=attachment,
            random_id=_rand_id(),
        )

    async def send_typing(self, external_id: str) -> None:
        try:
            await self.api.messages.set_activity(user_id=int(external_id), type="typing")
        except Exception:
            pass


async def run_vk_bot() -> None:
    """Long Poll loop for the VK community bot. No-op if credentials missing."""
    from config import VK_GROUP_TOKEN, VK_GROUP_ID

    if not VK_GROUP_TOKEN:
        print("[vk] VK_GROUP_TOKEN not set — VK channel disabled")
        return

    from vkbottle import Bot
    from vkbottle.bot import Message
    from channels.router import get_router
    from channels.vk_handlers import handle_vk_message

    bot = Bot(token=VK_GROUP_TOKEN)
    if VK_GROUP_ID:
        bot.group_id = int(VK_GROUP_ID)

    adapter = VKAdapter(bot.api)
    get_router().register(adapter)
    print("[vk] Channel registered, starting Long Poll...")

    @bot.on.message()
    async def on_message(message: Message):
        try:
            await handle_vk_message(message, adapter)
        except Exception as e:
            print(f"[vk] message handler error: {e}")
            try:
                await message.answer("Произошла ошибка. Попробуй ещё раз.")
            except Exception:
                pass

    await bot.run_polling()
