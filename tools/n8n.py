import httpx
from db.client import get_db


def get_integrations(user_id: str) -> list[dict]:
    db = get_db()
    result = db.table("integrations").select("*").eq("user_id", user_id).execute()
    return result.data


def list_integrations_for_user(user_id: str) -> list[dict]:
    integrations = get_integrations(user_id)
    return [{"type": i["type"], "config": i.get("config") or {}} for i in integrations]


async def call_integration(user_id: str, integration_type: str, payload: dict) -> dict:
    integrations = get_integrations(user_id)
    target = next((i for i in integrations if i["type"] == integration_type), None)
    if not target:
        return {
            "status": "error",
            "error": f"Integration '{integration_type}' not configured for this user",
        }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                target["webhook_url"],
                json={"payload": payload, "config": target["config"]},
            )
            return {"status": "ok", "response": response.json() if response.content else {}}
        except Exception as e:
            return {"status": "error", "error": str(e)}
