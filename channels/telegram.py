"""Telegram Bot API channel adapter."""

from io import BytesIO
from telegram import Bot, InputFile
from channels.base import ChannelAdapter


class TelegramAdapter(ChannelAdapter):
    channel = "telegram"

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_text(
        self,
        external_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        kwargs: dict = {"chat_id": int(external_id), "text": text}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
            try:
                await self.bot.send_message(**kwargs)
                return
            except Exception:
                kwargs.pop("parse_mode", None)
        await self.bot.send_message(**kwargs)

    async def send_photo(
        self,
        external_id: str,
        photo: bytes,
        caption: str | None = None,
    ) -> None:
        photo_file = InputFile(BytesIO(photo), filename="screenshot.png")
        await self.bot.send_photo(
            chat_id=int(external_id),
            photo=photo_file,
            caption=caption,
        )

    async def send_typing(self, external_id: str) -> None:
        await self.bot.send_chat_action(chat_id=int(external_id), action="typing")
