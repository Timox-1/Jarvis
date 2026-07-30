"""Shared inbound message processing for all channels."""

from __future__ import annotations

from channels.base import DeliveryContext
from channels.router import get_router
from bot.agent import run_agent
from tools.memory import get_history, save_message


async def process_text(
    user_id: str,
    text: str,
    delivery: DeliveryContext,
) -> str:
    router = get_router()
    await router.send_typing(delivery.channel, delivery.external_id)

    history = get_history(user_id)
    save_message(user_id, "user", text)

    error_response = None
    try:
        response = await run_agent(user_id, text, history, delivery=delivery)
    except Exception as e:
        print(f"[agent error] user={user_id} channel={delivery.channel}: {e}")
        error_response = "Произошла ошибка при обработке запроса. Попробуй ещё раз."
        response = error_response

    if not error_response:
        save_message(user_id, "assistant", response)

    return response
