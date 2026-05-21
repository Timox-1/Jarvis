from db.client import get_db

HISTORY_LIMIT = 20


def get_or_create_user(telegram_id: int, name: str) -> str:
    db = get_db()
    result = db.table("users").select("id").eq("telegram_id", telegram_id).execute()
    if result.data:
        return result.data[0]["id"]
    new_user = db.table("users").insert({
        "telegram_id": telegram_id,
        "name": name,
        "is_active": True,
        "plan": "free",
    }).execute()
    return new_user.data[0]["id"]


def is_user_allowed(telegram_id: int) -> bool:
    from config import ALLOWED_TELEGRAM_IDS
    if telegram_id in ALLOWED_TELEGRAM_IDS:
        return True
    db = get_db()
    result = db.table("users").select("is_active").eq("telegram_id", telegram_id).execute()
    if result.data and result.data[0]["is_active"]:
        return True
    return False


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
    db = get_db()
    result = db.table("user_memory").select("key,value").eq("user_id", user_id).execute()
    return {row["key"]: row["value"] for row in result.data}


def save_memory(user_id: str, key: str, value: str) -> str:
    db = get_db()
    db.table("user_memory").upsert({
        "user_id": user_id,
        "key": key,
        "value": value,
        "updated_at": "now()",
    }, on_conflict="user_id,key").execute()
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
