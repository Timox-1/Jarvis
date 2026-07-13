from db.client import get_db
from tools.resolve import resolve_row


def _resolve_contact(user_id: str, contact_ref: str) -> tuple[dict | None, str | None]:
    """Resolve a contact by UUID or by name fragment."""
    return resolve_row(
        "contacts",
        user_id,
        contact_ref,
        label_field="name",
        entity_name="Контакт",
    )


def add_contact_note(user_id: str, contact_id: str, text: str) -> str:
    """Save a note about a contact. Accepts a contact UUID or a fragment of the name."""
    contact, error = _resolve_contact(user_id, contact_id)
    if error:
        return error

    db = get_db()
    db.table("contact_notes").insert({
        "contact_id": contact["id"],
        "user_id": user_id,
        "text": text,
    }).execute()

    return f"Заметка сохранена по контакту {contact['name']}"


def list_contact_notes(user_id: str, contact_id: str) -> list[dict] | str:
    """List notes for a contact. Accepts a contact UUID or a fragment of the name."""
    contact, error = _resolve_contact(user_id, contact_id)
    if error:
        return error

    db = get_db()
    return (db.table("contact_notes")
            .select("id, text, created_at")
            .eq("contact_id", contact["id"])
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()).data
