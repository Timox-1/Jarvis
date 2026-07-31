"""
Universal projects — containers for dump & sort.

Client creates a project, dumps raw info; agent classifies into tasks,
expenses, contacts, reminders + always keeps a raw project note.
"""

from __future__ import annotations

from datetime import datetime, timezone

from db.client import get_db
from tools.resolve import resolve_row


def resolve_project(
    user_id: str,
    ref: str | None,
    *,
    allow_active: bool = True,
    statuses: list[str] | None = None,
) -> tuple[dict | None, str | None]:
    """Resolve project by UUID/name, or fall back to user's active project."""
    db = get_db()

    if ref:
        open_statuses = statuses or ["active", "archived"]
        project, error = resolve_row(
            "projects",
            user_id,
            ref,
            label_field="name",
            entity_name="Проект",
            status_field="status",
            open_statuses=open_statuses,
        )
        return project, error

    if not allow_active:
        return None, "Укажи проект (имя или id)"

    user = (
        db.table("users")
        .select("active_project_id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    ).data
    active_id = user[0]["active_project_id"] if user else None
    if not active_id:
        return None, "Нет активного проекта. Создай (create_project) или выбери (set_active_project)."

    found = (
        db.table("projects")
        .select("*")
        .eq("id", active_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data
    if not found:
        return None, "Активный проект не найден — выбери другой через set_active_project"
    return found[0], None


def get_active_project(user_id: str) -> dict | None:
    project, _ = resolve_project(user_id, None, allow_active=True)
    return project


def list_projects_preview(user_id: str, limit: int = 10) -> list[dict]:
    db = get_db()
    rows = (
        db.table("projects")
        .select("id, name, status")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    ).data
    return rows or []


def create_project(
    user_id: str,
    name: str,
    description: str | None = None,
    set_active: bool = True,
) -> str:
    db = get_db()
    name = (name or "").strip()
    if not name:
        return "Название проекта пустое"

    existing = (
        db.table("projects")
        .select("id, name, status")
        .eq("user_id", user_id)
        .ilike("name", name)
        .limit(1)
        .execute()
    ).data
    if existing:
        proj = existing[0]
        if proj["status"] == "archived":
            db.table("projects").update({
                "status": "active",
                "description": description,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", proj["id"]).execute()
            if set_active:
                set_active_project(user_id, proj["id"])
            return f"Проект восстановлен из архива: {proj['name']}" + (
                " (активный)" if set_active else ""
            )
        if set_active:
            set_active_project(user_id, proj["id"])
        return f"Проект уже есть: {proj['name']}" + (" — сделал активным" if set_active else "")

    row = {
        "user_id": user_id,
        "name": name,
        "status": "active",
    }
    if description:
        row["description"] = description

    inserted = db.table("projects").insert(row).execute()
    project_id = inserted.data[0]["id"]
    if set_active:
        set_active_project(user_id, project_id)
    return f"Проект создан: {name}" + (" (активный — кидай инфу сюда)" if set_active else "")


def list_projects(user_id: str, status: str = "active") -> list[dict]:
    db = get_db()
    query = db.table("projects").select("id, name, description, status, created_at, updated_at").eq(
        "user_id", user_id
    )
    if status and status != "all":
        query = query.eq("status", status)
    return query.order("updated_at", desc=True).execute().data or []


def set_active_project(user_id: str, project: str) -> str:
    proj, error = resolve_project(user_id, project, allow_active=False, statuses=["active", "archived"])
    if error:
        return error

    db = get_db()
    if proj["status"] == "archived":
        db.table("projects").update({
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", proj["id"]).execute()

    db.table("users").update({"active_project_id": proj["id"]}).eq("id", user_id).execute()
    db.table("projects").update({
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", proj["id"]).execute()
    return f"Активный проект: {proj['name']}. Кидай инфу — разложу."


def clear_active_project(user_id: str) -> str:
    db = get_db()
    db.table("users").update({"active_project_id": None}).eq("id", user_id).execute()
    return "Активный проект сброшен"


def archive_project(user_id: str, project: str | None = None) -> str:
    proj, error = resolve_project(user_id, project, allow_active=True)
    if error:
        return error

    db = get_db()
    db.table("projects").update({
        "status": "archived",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", proj["id"]).execute()

    user = (
        db.table("users")
        .select("active_project_id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    ).data
    if user and user[0].get("active_project_id") == proj["id"]:
        db.table("users").update({"active_project_id": None}).eq("id", user_id).execute()

    return f"Проект в архиве: {proj['name']}"


def rename_project(user_id: str, project: str, new_name: str) -> str:
    proj, error = resolve_project(user_id, project, allow_active=True)
    if error:
        return error

    new_name = (new_name or "").strip()
    if not new_name:
        return "Новое название пустое"

    db = get_db()
    try:
        db.table("projects").update({
            "name": new_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", proj["id"]).execute()
    except Exception as e:
        return f"Не удалось переименовать (возможно, имя занято): {e}"

    return f"Проект переименован: {proj['name']} → {new_name}"


def add_project_note(
    user_id: str,
    text: str,
    project: str | None = None,
    source: str = "user_dump",
) -> str:
    proj, error = resolve_project(user_id, project, allow_active=True)
    if error:
        return error

    text = (text or "").strip()
    if not text:
        return "Пустая заметка"

    if source not in ("user_dump", "agent"):
        source = "user_dump"

    db = get_db()
    db.table("project_notes").insert({
        "user_id": user_id,
        "project_id": proj["id"],
        "text": text,
        "source": source,
    }).execute()
    db.table("projects").update({
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", proj["id"]).execute()
    return f"Заметка в проекте «{proj['name']}» сохранена"


def list_project_notes(
    user_id: str,
    project: str | None = None,
    limit: int = 20,
) -> list[dict] | str:
    proj, error = resolve_project(user_id, project, allow_active=True)
    if error:
        return error

    db = get_db()
    rows = (
        db.table("project_notes")
        .select("id, text, source, created_at")
        .eq("user_id", user_id)
        .eq("project_id", proj["id"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data
    return rows or []


def link_contact_to_project(user_id: str, contact_id: str, project_id: str) -> None:
    db = get_db()
    contact = (
        db.table("contacts")
        .select("id")
        .eq("id", contact_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data
    if not contact:
        return
    existing = (
        db.table("project_contacts")
        .select("project_id")
        .eq("project_id", project_id)
        .eq("contact_id", contact_id)
        .limit(1)
        .execute()
    ).data
    if existing:
        return
    db.table("project_contacts").insert({
        "project_id": project_id,
        "contact_id": contact_id,
    }).execute()


def get_project_summary(user_id: str, project: str | None = None) -> dict | str:
    proj, error = resolve_project(user_id, project, allow_active=True)
    if error:
        return error

    db = get_db()
    pid = proj["id"]

    tasks = (
        db.table("tasks")
        .select("id, title, due_date, due_time, priority, status")
        .eq("user_id", user_id)
        .eq("project_id", pid)
        .in_("status", ["pending", "in_progress"])
        .order("due_date")
        .execute()
    ).data or []

    expenses = (
        db.table("expenses")
        .select("id, amount, category, description, date")
        .eq("user_id", user_id)
        .eq("project_id", pid)
        .order("date", desc=True)
        .limit(50)
        .execute()
    ).data or []
    expenses_total = round(sum(float(e["amount"]) for e in expenses), 2)

    contact_links = (
        db.table("project_contacts")
        .select("contact_id")
        .eq("project_id", pid)
        .execute()
    ).data or []
    contacts = []
    for link in contact_links:
        rows = (
            db.table("contacts")
            .select("id, name, phone, company, role")
            .eq("id", link["contact_id"])
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        ).data
        if rows:
            contacts.append(rows[0])

    reminders = (
        db.table("reminders")
        .select("id, text, fire_at")
        .eq("user_id", user_id)
        .eq("project_id", pid)
        .eq("done", False)
        .order("fire_at")
        .execute()
    ).data or []

    notes = (
        db.table("project_notes")
        .select("id, text, source, created_at")
        .eq("user_id", user_id)
        .eq("project_id", pid)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    ).data or []

    return {
        "project": {
            "id": proj["id"],
            "name": proj["name"],
            "description": proj.get("description"),
            "status": proj["status"],
        },
        "open_tasks": tasks,
        "expenses_total": expenses_total,
        "expenses_recent": expenses[:10],
        "contacts": contacts,
        "reminders": reminders,
        "recent_notes": notes,
        "counts": {
            "open_tasks": len(tasks),
            "expenses": len(expenses),
            "contacts": len(contacts),
            "reminders": len(reminders),
            "notes_shown": len(notes),
        },
    }
