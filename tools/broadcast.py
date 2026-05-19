"""
Broadcast messages to contacts via Telegram.
Uses a two-step process: prepare (preview) -> confirm (send).
"""

import asyncio
import json
from datetime import datetime, timezone
from db.client import get_db
from tools.contacts import get_contacts_for_broadcast


def prepare_broadcast(
    user_id: str,
    message: str,
    group_id: str = None,
    tag: str = None
) -> dict:
    """
    Prepare a broadcast - create pending record and return preview.
    Does NOT send yet - requires confirm_broadcast.

    Returns:
        dict with broadcast_id and recipient preview
    """
    db = get_db()

    # Get contacts to broadcast to
    contacts = get_contacts_for_broadcast(user_id, group_id=group_id, tag=tag)

    if not contacts:
        return {
            "status": "error",
            "error": "Нет контактов для рассылки. Добавьте контакты с telegram_id или telegram_username."
        }

    # Create pending broadcast record
    broadcast = db.table("broadcasts").insert({
        "user_id": user_id,
        "message": message,
        "recipient_count": len(contacts),
        "status": "pending_confirmation"
    }).execute()

    broadcast_id = broadcast.data[0]["id"]

    # Store recipient IDs in a separate field or we'll refetch on confirm
    recipient_names = [
        f"{c['name']}" + (f" ({c.get('company')})" if c.get('company') else "")
        for c in contacts
    ]

    return {
        "status": "pending",
        "broadcast_id": broadcast_id,
        "message_preview": message[:100] + ("..." if len(message) > 100 else ""),
        "recipient_count": len(contacts),
        "recipients": recipient_names[:10],  # Show first 10
        "more_recipients": max(0, len(contacts) - 10),
        "instruction": "Для отправки подтвердите командой confirm_broadcast"
    }


async def confirm_broadcast(
    bot,
    user_id: str,
    broadcast_id: str
) -> dict:
    """
    Confirm and execute a pending broadcast.

    Args:
        bot: Telegram bot instance
        user_id: Owner user ID
        broadcast_id: ID of pending broadcast

    Returns:
        dict with send results
    """
    db = get_db()

    # Get broadcast record
    broadcast = (db.table("broadcasts")
                 .select("*")
                 .eq("id", broadcast_id)
                 .eq("user_id", user_id)
                 .eq("status", "pending_confirmation")
                 .execute())

    if not broadcast.data:
        return {
            "status": "error",
            "error": "Рассылка не найдена или уже отправлена"
        }

    broadcast_data = broadcast.data[0]
    message = broadcast_data["message"]

    # Get contacts again
    contacts = get_contacts_for_broadcast(user_id)

    # Update status to sending
    db.table("broadcasts").update({
        "status": "sending"
    }).eq("id", broadcast_id).execute()

    sent_count = 0
    failed_count = 0
    errors = []

    for contact in contacts:
        telegram_id = contact.get("telegram_id")

        if not telegram_id:
            failed_count += 1
            continue

        try:
            await bot.send_message(chat_id=telegram_id, text=message)
            sent_count += 1
            # Rate limit protection
            await asyncio.sleep(0.05)
        except Exception as e:
            failed_count += 1
            errors.append(f"{contact['name']}: {str(e)[:50]}")

    # Update broadcast record
    db.table("broadcasts").update({
        "sent_count": sent_count,
        "failed_count": failed_count,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", broadcast_id).execute()

    result = {
        "status": "completed",
        "broadcast_id": broadcast_id,
        "sent": sent_count,
        "failed": failed_count,
    }

    if errors:
        result["errors"] = errors[:5]  # Show first 5 errors

    return result


def cancel_broadcast(user_id: str, broadcast_id: str) -> str:
    """Cancel a pending broadcast."""
    db = get_db()

    result = (db.table("broadcasts")
              .delete()
              .eq("id", broadcast_id)
              .eq("user_id", user_id)
              .eq("status", "pending_confirmation")
              .execute())

    if result.data:
        return "Рассылка отменена"
    return "Рассылка не найдена или уже отправлена"


def get_broadcast_history(user_id: str, limit: int = 10) -> list[dict]:
    """Get recent broadcast history."""
    db = get_db()

    result = (db.table("broadcasts")
              .select("id, message, recipient_count, sent_count, failed_count, status, created_at")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .limit(limit)
              .execute())

    return result.data
