from datetime import datetime, timezone
from db.client import get_db
from tools.resolve import resolve_row


def set_reminder(user_id: str, text: str, fire_at: str, project_id: str = None) -> str:
    db = get_db()
    row = {
        "user_id": user_id,
        "text": text,
        "fire_at": fire_at,
        "done": False,
    }
    if project_id:
        row["project_id"] = project_id
    db.table("reminders").insert(row).execute()
    suffix = " [проект]" if project_id else ""
    return f"Напоминание установлено: {text}{suffix}"


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
    """Delete a reminder. Accepts a UUID or a fragment of the reminder text."""
    reminder, error = resolve_row(
        "reminders",
        user_id,
        reminder_id,
        label_field="text",
        entity_name="Напоминание",
        status_field="done",
        open_statuses=[False],
    )
    if error:
        return error

    db = get_db()
    db.table("reminders").delete().eq("id", reminder["id"]).execute()
    return f"Напоминание удалено: {reminder['text']}"


async def check_and_fire_reminders(_bot=None) -> None:
    """Fire due reminders via ChannelRouter (all linked identities)."""
    from channels.router import get_router

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    reminders = (db.table("reminders")
                 .select("id, text, user_id")
                 .eq("done", False)
                 .lte("fire_at", now)
                 .execute()).data

    if not reminders:
        return

    router = get_router()
    for reminder in reminders:
        try:
            sent = await router.send_text_to_user(
                reminder["user_id"],
                f"⏰ {reminder['text']}",
            )
            if sent:
                db.table("reminders").update({"done": True}).eq("id", reminder["id"]).execute()
        except Exception as e:
            print(f"[reminder] fire error id={reminder['id']}: {e}")
