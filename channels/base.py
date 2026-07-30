"""Channel transport abstraction — one agent, many messengers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryContext:
    """Where to send proactive replies (screenshots, etc.) for the current turn."""
    channel: str
    external_id: str


class ChannelAdapter(ABC):
    channel: str

    @abstractmethod
    async def send_text(
        self,
        external_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        ...

    @abstractmethod
    async def send_photo(
        self,
        external_id: str,
        photo: bytes,
        caption: str | None = None,
    ) -> None:
        ...

    async def send_typing(self, external_id: str) -> None:
        """Optional typing indicator. Default: no-op."""
        return None
