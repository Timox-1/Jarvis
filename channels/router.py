"""Registry of channel adapters + helpers to deliver by user_id."""

from __future__ import annotations

from channels.base import ChannelAdapter

_router: "ChannelRouter | None" = None


class ChannelRouter:
    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel] = adapter

    def get(self, channel: str) -> ChannelAdapter | None:
        return self._adapters.get(channel)

    def has(self, channel: str) -> bool:
        return channel in self._adapters

    async def send_text(
        self,
        channel: str,
        external_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        adapter = self._adapters.get(channel)
        if not adapter:
            raise RuntimeError(f"Channel not registered: {channel}")
        await adapter.send_text(external_id, text, parse_mode=parse_mode)

    async def send_photo(
        self,
        channel: str,
        external_id: str,
        photo: bytes,
        caption: str | None = None,
    ) -> None:
        adapter = self._adapters.get(channel)
        if not adapter:
            raise RuntimeError(f"Channel not registered: {channel}")
        await adapter.send_photo(external_id, photo, caption=caption)

    async def send_typing(self, channel: str, external_id: str) -> None:
        adapter = self._adapters.get(channel)
        if adapter:
            await adapter.send_typing(external_id)

    async def send_text_to_user(
        self,
        user_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> list[str]:
        """Send to all linked identities. Returns list of channels that received it."""
        from tools.memory import list_user_identities

        sent: list[str] = []
        for ident in list_user_identities(user_id):
            channel = ident["channel"]
            if channel not in self._adapters:
                continue
            try:
                await self.send_text(channel, ident["external_id"], text, parse_mode=parse_mode)
                sent.append(channel)
            except Exception as e:
                print(f"[channel] send_text failed {channel}/{ident['external_id']}: {e}")
        return sent


def get_router() -> ChannelRouter:
    global _router
    if _router is None:
        _router = ChannelRouter()
    return _router


def set_router(router: ChannelRouter) -> None:
    global _router
    _router = router
