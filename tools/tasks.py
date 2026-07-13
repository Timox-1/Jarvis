"""
Tasks/TODO management for the assistant.
"""

from datetime import datetime, date, timedelta, timezone
from db.client import get_db
from tools.resolve import resolve_row

MOSCOW_TZ = timezone(timedelta(hours=3))
KEMEROVO_TZ = timezone(timedelta(hours=7))

PRIORITY_ORDER = {"urgent": 4, "high": 3, "normal": 2, "low": 1}


def add_task(
    user_id: str,
    title: str,
    description: str = None,
    due_date: str = None,
    due_time: str = None,
    priority: str = "normal"
) -> str:
    """Add a new task to the user's TODO list."""
    db = get_db()

    data = {
        "user_id": user_id,
        "title": title,
        "priority": priority,
        "status": "pending",
    }

    if description:
        data["description"] = description
    if due_date:
        data["due_date"] = due_date
    if due_time:
        data["due_time"] = due_time

    db.table("tasks").insert(data).execute()

    result = f"Задача добавлена: {title}"
    if due_date:
        result += f" (срок: {due_date}"
        if due_time:
            result += f" {due_time}"
        result += ")"
    if priority != "normal":
        result += f" [{priority}]"

    return result


def list_tasks(
    user_id: str,
    status: str = None,
    date_filter: str = None,
    include_completed: bool = False
) -> list[dict]:
    """
    List user's tasks.

    Args:
        user_id: User ID
        status: Filter by status (pending, in_progress, done)
        date_filter: 'today', 'tomorrow', 'week', or specific date YYYY-MM-DD
        include_completed: Include completed tasks
    """
    db = get_db()

    query = db.table("tasks").select("*").eq("user_id", user_id)

    if status:
        query = query.eq("status", status)
    elif not include_completed:
        query = query.in_("status", ["pending", "in_progress"])

    if date_filter:
        today = datetime.now(KEMEROVO_TZ).date()

        if date_filter == "today":
            query = query.eq("due_date", today.isoformat())
        elif date_filter == "tomorrow":
            tomorrow = today + timedelta(days=1)
            query = query.eq("due_date", tomorrow.isoformat())
        elif date_filter == "week":
            week_end = today + timedelta(days=7)
            query = query.gte("due_date", today.isoformat()).lte("due_date", week_end.isoformat())
        else:
            # Specific date
            query = query.eq("due_date", date_filter)

    query = query.order("due_date", nullsfirst=False)

    result = query.execute()
    return sorted(
        result.data,
        key=lambda t: (
            t.get("due_date") or "9999-99-99",
            -PRIORITY_ORDER.get(t.get("priority", "normal"), 2),
        ),
    )


def _resolve_task(user_id: str, task_ref: str) -> tuple[dict | None, str | None]:
    """Resolve a task by UUID or by title fragment (open tasks only)."""
    return resolve_row(
        "tasks",
        user_id,
        task_ref,
        label_field="title",
        entity_name="Задача",
        status_field="status",
        open_statuses=["pending", "in_progress"],
    )


def complete_task(user_id: str, task_id: str) -> str:
    """Mark a task as completed. Accepts a task UUID or a fragment of its title."""
    task, error = _resolve_task(user_id, task_id)
    if error:
        return error

    db = get_db()
    db.table("tasks").update({
        "status": "done",
        "completed_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", task["id"]).execute()

    return f"Задача выполнена: {task['title']}"


def delete_task(user_id: str, task_id: str) -> str:
    """Delete a task. Accepts a task UUID or a fragment of its title."""
    task, error = _resolve_task(user_id, task_id)
    if error:
        return error

    db = get_db()
    db.table("tasks").delete().eq("id", task["id"]).execute()

    return f"Задача удалена: {task['title']}"


def update_task(
    user_id: str,
    task_id: str,
    title: str = None,
    description: str = None,
    due_date: str = None,
    due_time: str = None,
    priority: str = None,
    status: str = None
) -> str:
    """Update a task. Accepts a task UUID or a fragment of its title."""
    task, error = _resolve_task(user_id, task_id)
    if error:
        return error

    db = get_db()
    updates = {}
    if title:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if due_date:
        updates["due_date"] = due_date
    if due_time:
        updates["due_time"] = due_time
    if priority:
        updates["priority"] = priority
    if status:
        updates["status"] = status
        if status == "done":
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()

    if not updates:
        return "Нечего обновлять"

    db.table("tasks").update(updates).eq("id", task["id"]).execute()

    return f"Задача обновлена: {title or task['title']}"


def get_today_summary(user_id: str) -> dict:
    """Get summary of today's tasks and upcoming items."""
    db = get_db()
    today = datetime.now(KEMEROVO_TZ).date()
    tomorrow = today + timedelta(days=1)

    # Today's tasks
    today_tasks = sorted(
        (db.table("tasks")
         .select("*")
         .eq("user_id", user_id)
         .eq("due_date", today.isoformat())
         .in_("status", ["pending", "in_progress"])
         .execute()).data,
        key=lambda t: -PRIORITY_ORDER.get(t.get("priority", "normal"), 2),
    )

    # Overdue tasks
    overdue = (db.table("tasks")
               .select("*")
               .eq("user_id", user_id)
               .lt("due_date", today.isoformat())
               .in_("status", ["pending", "in_progress"])
               .order("due_date")
               .execute()).data

    # Tomorrow's tasks
    tomorrow_tasks = (db.table("tasks")
                      .select("*")
                      .eq("user_id", user_id)
                      .eq("due_date", tomorrow.isoformat())
                      .in_("status", ["pending", "in_progress"])
                      .execute()).data

    # Pending reminders for today
    now = datetime.now(timezone.utc)
    end_of_day = datetime.combine(today, datetime.max.time()).replace(tzinfo=MOSCOW_TZ)

    reminders = (db.table("reminders")
                 .select("*")
                 .eq("user_id", user_id)
                 .eq("done", False)
                 .lte("fire_at", end_of_day.isoformat())
                 .order("fire_at")
                 .execute()).data

    return {
        "date": today.isoformat(),
        "overdue": overdue,
        "today": today_tasks,
        "tomorrow": tomorrow_tasks,
        "reminders_today": reminders,
        "summary": {
            "overdue_count": len(overdue),
            "today_count": len(today_tasks),
            "tomorrow_count": len(tomorrow_tasks),
            "reminders_count": len(reminders),
        }
    }
