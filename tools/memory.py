from __future__ import annotations

from db.client import get_db

HISTORY_LIMIT = 20

# Credentials live in user_memory because IMAP/SMTP need the password itself,
# but they must never reach the model: read_memory feeds the system prompt, so
# anything matching these suffixes would be sent to the LLM provider on every
# request. Consumers that genuinely need the value (tools/email.py) read the row
# straight from the table.
SECRET_KEY_SUFFIXES = ("_password", "_token", "_secret", "_key")

VALID_PLANS = ("free", "trial", "friend", "base", "pro", "business")


def is_secret_key(key: str) -> bool:
    return key.lower().endswith(SECRET_KEY_SUFFIXES)


def _is_telegram_admin(telegram_id: int) -> bool:
    from config import ADMIN_TELEGRAM_IDS, ALLOWED_TELEGRAM_IDS
    return telegram_id in ADMIN_TELEGRAM_IDS or telegram_id in ALLOWED_TELEGRAM_IDS


def list_user_identities(user_id: str) -> list[dict]:
    db = get_db()
    result = (
        db.table("user_identities")
        .select("channel, external_id")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


def get_user_by_identity(channel: str, external_id: str | int) -> dict | None:
    db = get_db()
    ext = str(external_id)
    ident = (
        db.table("user_identities")
        .select("user_id")
        .eq("channel", channel)
        .eq("external_id", ext)
        .limit(1)
        .execute()
    ).data
    if not ident:
        if channel == "telegram":
            legacy = (
                db.table("users")
                .select("id, is_active, plan, paid_until, name, telegram_id")
                .eq("telegram_id", int(ext))
                .limit(1)
                .execute()
            ).data
            if legacy:
                _ensure_identity(legacy[0]["id"], channel, ext)
                return legacy[0]
        return None

    user = (
        db.table("users")
        .select("id, is_active, plan, paid_until, name, telegram_id")
        .eq("id", ident[0]["user_id"])
        .limit(1)
        .execute()
    ).data
    return user[0] if user else None


def _ensure_identity(user_id: str, channel: str, external_id: str) -> None:
    db = get_db()
    existing = (
        db.table("user_identities")
        .select("id")
        .eq("channel", channel)
        .eq("external_id", external_id)
        .limit(1)
        .execute()
    ).data
    if existing:
        return
    db.table("user_identities").insert({
        "user_id": user_id,
        "channel": channel,
        "external_id": external_id,
    }).execute()


def get_or_create_user(channel: str, external_id: str | int, name: str) -> str:
    """Resolve or create a user for a channel identity.

    New users are inactive by default. Telegram admins / ALLOWED whitelist
    are auto-activated.
    """
    db = get_db()
    ext = str(external_id)

    existing = get_user_by_identity(channel, ext)
    if existing:
        if name and name != existing.get("name"):
            db.table("users").update({"name": name}).eq("id", existing["id"]).execute()
        return existing["id"]

    auto_active = channel == "telegram" and _is_telegram_admin(int(ext))
    row: dict = {
        "name": name,
        "is_active": auto_active,
        "plan": "pro" if auto_active else "free",
    }
    if channel == "telegram":
        row["telegram_id"] = int(ext)

    new_user = db.table("users").insert(row).execute()
    user_id = new_user.data[0]["id"]
    _ensure_identity(user_id, channel, ext)
    return user_id


def is_user_allowed(channel: str, external_id: str | int) -> bool:
    if channel == "telegram" and _is_telegram_admin(int(external_id)):
        return True

    user = get_user_by_identity(channel, external_id)
    if user and user.get("is_active"):
        return True
    return False


def invite_user(
    channel: str,
    external_id: str | int,
    plan: str = "trial",
    paid_until: str | None = None,
    name: str | None = None,
) -> dict:
    """Create or activate a user for the given channel identity."""
    if plan not in VALID_PLANS:
        raise ValueError(f"Неизвестный план: {plan}. Допустимо: {', '.join(VALID_PLANS)}")

    db = get_db()
    ext = str(external_id)
    user = get_user_by_identity(channel, ext)

    updates: dict = {
        "is_active": True,
        "plan": plan,
    }
    if paid_until:
        updates["paid_until"] = paid_until
    if name:
        updates["name"] = name

    if user:
        db.table("users").update(updates).eq("id", user["id"]).execute()
        user_id = user["id"]
        created = False
    else:
        row = {
            "name": name or f"{channel}:{ext}",
            "is_active": True,
            "plan": plan,
        }
        if paid_until:
            row["paid_until"] = paid_until
        if channel == "telegram":
            row["telegram_id"] = int(ext)
        inserted = db.table("users").insert(row).execute()
        user_id = inserted.data[0]["id"]
        _ensure_identity(user_id, channel, ext)
        created = True

    return {
        "user_id": user_id,
        "channel": channel,
        "external_id": ext,
        "plan": plan,
        "paid_until": paid_until,
        "created": created,
    }


def link_identity(user_id: str, channel: str, external_id: str | int) -> str:
    """Attach an additional channel identity to an existing user."""
    ext = str(external_id)
    existing = get_user_by_identity(channel, ext)
    if existing and existing["id"] != user_id:
        raise ValueError(f"Идентичность {channel}:{ext} уже привязана к другому пользователю")

    _ensure_identity(user_id, channel, ext)
    if channel == "telegram":
        get_db().table("users").update({"telegram_id": int(ext)}).eq("id", user_id).execute()
    return f"Привязано {channel}:{ext} → {user_id}"


def find_user_id_by_telegram(telegram_id: int) -> str | None:
    user = get_user_by_identity("telegram", telegram_id)
    return user["id"] if user else None


def get_user_profile(user_id: str) -> dict | None:
    db = get_db()
    result = (
        db.table("users")
        .select("id, name, is_active, plan, paid_until, telegram_id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    ).data
    return result[0] if result else None


def save_message(user_id: str, role: str, content: str) -> None:
    db = get_db()
    db.table("messages").insert({
        "user_id": user_id,
        "role": role,
        "content": content,
    }).execute()


def get_history(user_id: str) -> list[dict]:
    db = get_db()
    result = (
        db.table("messages")
        .select("role,content,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(HISTORY_LIMIT)
        .execute()
    )
    messages = list(reversed(result.data))
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def read_memory(user_id: str) -> dict:
    """Facts about the user for the system prompt.

    Secret values are masked, not dropped: the model still needs to know a credential
    is on file (otherwise it keeps asking the user for it), but must never see it.
    """
    db = get_db()
    result = db.table("user_memory").select("key,value").eq("user_id", user_id).execute()
    return {
        row["key"]: "<saved, hidden from the model>" if is_secret_key(row["key"]) else row["value"]
        for row in result.data
    }


def save_memory(user_id: str, key: str, value: str) -> str:
    db = get_db()
    db.table("user_memory").upsert({
        "user_id": user_id,
        "key": key,
        "value": value,
        "updated_at": "now()",
    }, on_conflict="user_id,key").execute()
    if is_secret_key(key):
        # The return value is shown in chat and stored in `messages`.
        return f"Saved: {key} (value hidden)"
    return f"Saved: {key} = {value}"


def forget_memory(user_id: str, key: str) -> str:
    db = get_db()
    db.table("user_memory").delete().eq("user_id", user_id).eq("key", key).execute()
    return f"Forgotten: {key}"


def clear_history(user_id: str) -> int:
    """Clear all messages for a user. Returns count of deleted messages."""
    db = get_db()
    result = db.table("messages").delete().eq("user_id", user_id).execute()
    return len(result.data) if result.data else 0


def access_denied_text() -> str:
    from config import ACCESS_CONTACT
    return (
        "Доступ закрыт — Джарвис работает по подписке.\n\n"
        f"Напиши {ACCESS_CONTACT}, чтобы подключить доступ."
    )
