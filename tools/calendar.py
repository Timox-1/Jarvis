from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import caldav
from icalendar import Calendar, Event
import uuid

from db.client import get_db
from config import YANDEX_CALENDAR_CLIENT_ID, YANDEX_CALENDAR_CLIENT_SECRET

YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
CALDAV_BASE_URL = "https://caldav.yandex.ru"


def _get_integration(user_id: str) -> dict | None:
    db = get_db()
    result = (db.table("user_integrations")
              .select("*")
              .eq("user_id", user_id)
              .eq("provider", "yandex_calendar")
              .execute())
    return result.data[0] if result.data else None


def _refresh_token(integration: dict) -> dict:
    resp = httpx.post(YANDEX_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": integration["refresh_token"],
        "client_id": YANDEX_CALENDAR_CLIENT_ID,
        "client_secret": YANDEX_CALENDAR_CLIENT_SECRET,
    })
    resp.raise_for_status()
    data = resp.json()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    db = get_db()
    db.table("user_integrations").update({
        "access_token": data["access_token"],
        "expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", integration["id"]).execute()

    integration["access_token"] = data["access_token"]
    integration["expires_at"] = expires_at.isoformat()
    return integration


def _get_valid_token(user_id: str) -> tuple[str, str]:
    integration = _get_integration(user_id)
    if not integration:
        raise ValueError("Яндекс Календарь не подключён. Используй /connect_calendar")

    expires_at = datetime.fromisoformat(integration["expires_at"]) if integration.get("expires_at") else None
    if expires_at and datetime.now(timezone.utc) >= expires_at - timedelta(minutes=5):
        integration = _refresh_token(integration)

    return integration["access_token"], integration.get("yandex_login", "")


def _get_caldav_client(access_token: str) -> caldav.DAVClient:
    return caldav.DAVClient(
        url=CALDAV_BASE_URL,
        headers={"Authorization": f"OAuth {access_token}"},
    )


def list_events(user_id: str, start_date: str, end_date: str) -> list[dict]:
    """List calendar events in date range. start_date/end_date: 'YYYY-MM-DD'"""
    access_token, _ = _get_valid_token(user_id)
    client = _get_caldav_client(access_token)

    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        return []

    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )

    events = []
    for calendar in calendars:
        try:
            results = calendar.date_search(start=start, end=end, expand=True)
            for event in results:
                cal = Calendar.from_ical(event.data)
                for component in cal.walk():
                    if component.name == "VEVENT":
                        dtstart = component.get("DTSTART")
                        dtend = component.get("DTEND")
                        events.append({
                            "uid": str(component.get("UID", "")),
                            "title": str(component.get("SUMMARY", "Без названия")),
                            "start": dtstart.dt.isoformat() if dtstart else "",
                            "end": dtend.dt.isoformat() if dtend else "",
                            "description": str(component.get("DESCRIPTION", "")),
                            "calendar": str(calendar.name),
                        })
        except Exception:
            continue

    events.sort(key=lambda e: e["start"])
    return events


def create_event(
    user_id: str,
    title: str,
    start: str,
    end: str,
    description: str = "",
) -> str:
    """Create event. start/end: ISO datetime with timezone e.g. '2026-05-22T15:00:00+03:00'"""
    access_token, _ = _get_valid_token(user_id)
    client = _get_caldav_client(access_token)

    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise ValueError("Нет доступных календарей")

    calendar = calendars[0]
    event_uid = str(uuid.uuid4())
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    cal = Calendar()
    cal.add("prodid", "-//Jarvis Bot//RU")
    cal.add("version", "2.0")

    event = Event()
    event.add("uid", event_uid)
    event.add("summary", title)
    event.add("dtstart", start_dt)
    event.add("dtend", end_dt)
    if description:
        event.add("description", description)
    event.add("dtstamp", datetime.now(timezone.utc))

    cal.add_component(event)
    calendar.add_event(cal.to_ical().decode())

    return f"Событие создано: {title} (uid: {event_uid})"


def delete_event(user_id: str, event_uid: str) -> str:
    """Delete event by UID."""
    access_token, _ = _get_valid_token(user_id)
    client = _get_caldav_client(access_token)

    principal = client.principal()
    for calendar in principal.calendars():
        try:
            results = calendar.search(uid=event_uid)
            if results:
                results[0].delete()
                return "Событие удалено"
        except Exception:
            continue

    return "Событие не найдено"


def save_calendar_tokens(
    user_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    yandex_login: str,
) -> None:
    """Called by n8n after OAuth. Saves tokens to Supabase."""
    db = get_db()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    db.table("user_integrations").upsert({
        "user_id": user_id,
        "provider": "yandex_calendar",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at.isoformat(),
        "yandex_login": yandex_login,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id,provider").execute()
