"""
Contacts and broadcasts management.
"""

from db.client import get_db


def add_contact(
    user_id: str,
    name: str,
    phone: str = None,
    email: str = None,
    telegram_username: str = None,
    telegram_id: int = None,
    company: str = None,
    role: str = None,
    notes: str = None,
    tags: list[str] = None
) -> str:
    """Add a new contact to the address book."""
    db = get_db()

    data = {
        "user_id": user_id,
        "name": name,
    }

    if phone:
        data["phone"] = phone
    if email:
        data["email"] = email
    if telegram_username:
        data["telegram_username"] = telegram_username.lstrip("@")
    if telegram_id:
        data["telegram_id"] = telegram_id
    if company:
        data["company"] = company
    if role:
        data["role"] = role
    if notes:
        data["notes"] = notes
    if tags:
        data["tags"] = tags

    db.table("contacts").insert(data).execute()

    result = f"Контакт добавлен: {name}"
    if company:
        result += f" ({company})"

    return result


def list_contacts(
    user_id: str,
    search: str = None,
    tag: str = None,
    limit: int = 50
) -> list[dict]:
    """
    List user's contacts.

    Args:
        user_id: User ID
        search: Search by name, company, or notes
        tag: Filter by tag
        limit: Max results
    """
    db = get_db()

    query = db.table("contacts").select("*").eq("user_id", user_id)

    if search:
        query = query.or_(f"name.ilike.%{search}%,company.ilike.%{search}%")

    if tag:
        query = query.contains("tags", [tag])

    query = query.order("name").limit(limit)

    result = query.execute()
    return result.data


def get_contact(user_id: str, contact_id: str) -> dict | None:
    """Get a single contact by ID."""
    db = get_db()

    result = (db.table("contacts")
              .select("*")
              .eq("id", contact_id)
              .eq("user_id", user_id)
              .execute())

    return result.data[0] if result.data else None


def update_contact(
    user_id: str,
    contact_id: str,
    name: str = None,
    phone: str = None,
    email: str = None,
    telegram_username: str = None,
    company: str = None,
    role: str = None,
    notes: str = None,
    tags: list[str] = None
) -> str:
    """Update a contact."""
    db = get_db()

    contact = get_contact(user_id, contact_id)
    if not contact:
        return "Контакт не найден"

    updates = {}
    if name:
        updates["name"] = name
    if phone is not None:
        updates["phone"] = phone
    if email is not None:
        updates["email"] = email
    if telegram_username is not None:
        updates["telegram_username"] = telegram_username.lstrip("@") if telegram_username else None
    if company is not None:
        updates["company"] = company
    if role is not None:
        updates["role"] = role
    if notes is not None:
        updates["notes"] = notes
    if tags is not None:
        updates["tags"] = tags

    if not updates:
        return "Нечего обновлять"

    db.table("contacts").update(updates).eq("id", contact_id).execute()

    return f"Контакт обновлён: {name or contact['name']}"


def delete_contact(user_id: str, contact_id: str) -> str:
    """Delete a contact."""
    db = get_db()

    contact = get_contact(user_id, contact_id)
    if not contact:
        return "Контакт не найден"

    db.table("contacts").delete().eq("id", contact_id).execute()

    return f"Контакт удалён: {contact['name']}"


# --- Contact Groups ---

def create_contact_group(user_id: str, name: str, description: str = None) -> str:
    """Create a contact group for broadcasts."""
    db = get_db()

    data = {"user_id": user_id, "name": name}
    if description:
        data["description"] = description

    db.table("contact_groups").insert(data).execute()

    return f"Группа создана: {name}"


def list_contact_groups(user_id: str) -> list[dict]:
    """List user's contact groups."""
    db = get_db()

    result = (db.table("contact_groups")
              .select("*")
              .eq("user_id", user_id)
              .order("name")
              .execute())

    return result.data


def add_contact_to_group(user_id: str, contact_id: str, group_id: str) -> str:
    """Add a contact to a group."""
    db = get_db()

    # Verify ownership
    contact = get_contact(user_id, contact_id)
    if not contact:
        return "Контакт не найден"

    group = (db.table("contact_groups")
             .select("name")
             .eq("id", group_id)
             .eq("user_id", user_id)
             .execute())

    if not group.data:
        return "Группа не найдена"

    # Check if already in group
    existing = (db.table("contact_group_members")
                .select("*")
                .eq("contact_id", contact_id)
                .eq("group_id", group_id)
                .execute())

    if existing.data:
        return f"{contact['name']} уже в группе {group.data[0]['name']}"

    db.table("contact_group_members").insert({
        "contact_id": contact_id,
        "group_id": group_id,
    }).execute()

    return f"{contact['name']} добавлен в группу {group.data[0]['name']}"


def get_group_contacts(user_id: str, group_id: str) -> list[dict]:
    """Get all contacts in a group."""
    db = get_db()

    # Verify ownership
    group = (db.table("contact_groups")
             .select("name")
             .eq("id", group_id)
             .eq("user_id", user_id)
             .execute())

    if not group.data:
        return []

    # Get member IDs
    members = (db.table("contact_group_members")
               .select("contact_id")
               .eq("group_id", group_id)
               .execute())

    if not members.data:
        return []

    contact_ids = [m["contact_id"] for m in members.data]

    # Get contacts
    contacts = (db.table("contacts")
                .select("*")
                .in_("id", contact_ids)
                .order("name")
                .execute())

    return contacts.data


def get_contacts_for_broadcast(
    user_id: str,
    group_id: str = None,
    tag: str = None,
    contact_ids: list[str] = None
) -> list[dict]:
    """
    Get contacts for a broadcast.
    Can filter by group, tag, or specific IDs.
    Returns only contacts with telegram_id or telegram_username.
    """
    db = get_db()

    if group_id:
        contacts = get_group_contacts(user_id, group_id)
    elif contact_ids:
        contacts = (db.table("contacts")
                    .select("*")
                    .eq("user_id", user_id)
                    .in_("id", contact_ids)
                    .execute()).data
    elif tag:
        contacts = (db.table("contacts")
                    .select("*")
                    .eq("user_id", user_id)
                    .contains("tags", [tag])
                    .execute()).data
    else:
        contacts = (db.table("contacts")
                    .select("*")
                    .eq("user_id", user_id)
                    .execute()).data

    # Filter to only those we can message via Telegram
    return [c for c in contacts if c.get("telegram_id") or c.get("telegram_username")]
