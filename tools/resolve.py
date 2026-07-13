"""
Shared entity resolution: let tools accept a human reference (name/title) instead of a UUID.

GPT thinks in names, not UUIDs. A tool that hard-requires a UUID it has no way to know
will silently degrade into a polite "готово!" with nothing written to the DB.
"""

import re
from db.client import get_db

UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def is_uuid(value: str) -> bool:
    return bool(UUID_RE.match(value or ""))


def resolve_row(
    table: str,
    user_id: str,
    ref: str,
    label_field: str,
    entity_name: str,
    status_field: str = None,
    open_statuses: list[str] = None,
) -> tuple[dict | None, str | None]:
    """
    Resolve a row by UUID or by a fragment of its label (title/name/text).

    Returns (row, error_message) — exactly one of the two is set. The error text is
    written for GPT to act on: it names the next tool to call.
    """
    db = get_db()

    if is_uuid(ref):
        found = db.table(table).select("*").eq("id", ref).eq("user_id", user_id).execute().data
        if not found:
            return None, f"{entity_name} не найден(а) по id {ref}"
        return found[0], None

    query = db.table(table).select("*").eq("user_id", user_id)
    if status_field and open_statuses:
        query = query.in_(status_field, open_statuses)

    matches = query.ilike(label_field, f"%{ref}%").execute().data

    if not matches:
        return None, f"{entity_name} по запросу «{ref}» не найден(а). Посмотри список и уточни у пользователя."

    if len(matches) > 1:
        options = "\n".join(f"  • {m[label_field]} (id: {m['id']})" for m in matches)
        return None, (
            f"Под «{ref}» подходит несколько — уточни у пользователя, какой именно:\n{options}"
        )

    return matches[0], None
