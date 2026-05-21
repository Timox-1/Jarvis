from db.client import get_db


def add_contact_note(user_id: str, contact_id: str, text: str) -> str:
    db = get_db()

    contact = (db.table("contacts")
               .select("name")
               .eq("id", contact_id)
               .eq("user_id", user_id)
               .execute())
    if not contact.data:
        return "Контакт не найден"

    db.table("contact_notes").insert({
        "contact_id": contact_id,
        "user_id": user_id,
        "text": text,
    }).execute()

    return f"Заметка сохранена по контакту {contact.data[0]['name']}"


def list_contact_notes(user_id: str, contact_id: str) -> list[dict]:
    db = get_db()
    return (db.table("contact_notes")
            .select("id, text, created_at")
            .eq("contact_id", contact_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()).data
