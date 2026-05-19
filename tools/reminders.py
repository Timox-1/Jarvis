from datetime import datetime, timezone
from db.client import get_db


def set_reminder(user_id: str, text: str, fire_at: str) -> str:
    db = get_db()
    db.table("reminders").insert({
        "user_id": user_id,
        "text": text,
        "fire_at": fire_at,
        "done": False,
    }).execute()
    return f"Напоминание установлено: {text}"


def list_reminders(user_id: str) -> list[dict]:
    db = get_db()
    result = (db.table("reminders")
              .select("id, text, fire_at")
              .eq("user_id", user_id)
              .eq("done", False)
              .order("fire_at")
              .execute())
    return result.data


def delete_reminder(user_id: str, reminder_id: str) -> str:
    db = get_db()
    db.table("reminders").delete().eq("id", reminder_id).eq("user_id", user_id).execute()
    return "Напоминание удалено"


async def check_and_fire_reminders(bot) -> None:
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    reminders = (db.table("reminders")
                 .select("id, text, user_id")
                 .eq("done", False)
                 .lte("fire_at", now)
                 .execute()).data

    if not reminders:
        return

    user_ids = list({r["user_id"] for r in reminders})
    users = (db.table("users")
             .select("id, telegram_id")
             .in_("id", user_ids)
             .execute()).data
    user_map = {u["id"]: u["telegram_id"] for u in users}

    for reminder in reminders:
        telegram_id = user_map.get(reminder["user_id"])
        if not telegram_id:
            continue
        try:
            await bot.send_message(chat_id=telegram_id, text=f"⏰ {reminder['text']}")
            db.table("reminders").update({"done": True}).eq("id", reminder["id"]).execute()
        except Exception:
            pass
