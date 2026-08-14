"""User prefs: city, timezone offset, morning briefing time."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from db.client import get_db

DEFAULT_CITY = "Кемерово"
DEFAULT_OFFSET_HOURS = 7
DEFAULT_BRIEFING_TIME = "09:00"

_CITY_OFFSETS: dict[str, int] = {
    'калининград': 2,
    'москва': 3,
    'msk': 3,
    'мск': 3,
    'санкт-петербург': 3,
    'петербург': 3,
    'спб': 3,
    'питер': 3,
    'новороссийск': 3,
    'краснодар': 3,
    'сочи': 3,
    'ростов': 3,
    'ростов-на-дону': 3,
    'воронеж': 3,
    'нижний новгород': 3,
    'казань': 3,
    'тула': 3,
    'ярославль': 3,
    'тверь': 3,
    'вологда': 3,
    'мурманск': 3,
    'архангельск': 3,
    'смоленск': 3,
    'рязань': 3,
    'липецк': 3,
    'тамбов': 3,
    'пенза': 3,
    'ульяновск': 3,
    'чебоксары': 3,
    'киров': 3,
    'ставрополь': 3,
    'махачкала': 3,
    'грозный': 3,
    'нальчик': 3,
    'владикавказ': 3,
    'симферополь': 3,
    'севастополь': 3,
    'минск': 3,
    'волгоград': 3,
    'самара': 4,
    'тольятти': 4,
    'саратов': 4,
    'астрахань': 4,
    'уфа': 4,
    'ижевск': 4,
    'екатеринбург': 5,
    'ебург': 5,
    'екб': 5,
    'челябинск': 5,
    'пермь': 5,
    'тюмень': 5,
    'курган': 5,
    'магнитогорск': 5,
    'нижний тагил': 5,
    'сургут': 5,
    'ханты-мансийск': 5,
    'омск': 6,
    'новосибирск': 7,
    'новосиб': 7,
    'нск': 7,
    'барнаул': 7,
    'томск': 7,
    'кемерово': 7,
    'новокузнецк': 7,
    'красноярск': 7,
    'абакан': 7,
    'кызыл': 7,
    'горно-алтайск': 7,
    'бийск': 7,
    'прокопьевск': 7,
    'иркутск': 8,
    'улан-удэ': 8,
    'улан удэ': 8,
    'чита': 8,
    'братск': 8,
    'якутск': 9,
    'благовещенск': 9,
    'владивосток': 10,
    'хабаровск': 10,
    'южно-сахалинск': 10,
    'находка': 10,
    'магадан': 11,
    'петропавловск-камчатский': 12,
    'камчатка': 12,
    'анадырь': 12,
}


def _normalize_city(city: str) -> str:
    c = city.strip().lower().replace("ё", "е")
    c = re.sub(r"\s+", " ", c)
    c = c.replace("г.", "").replace("город ", "").strip()
    return c


def resolve_city(city: str) -> tuple[str | None, int | None, str | None]:
    if not city or not city.strip():
        return None, None, "Укажи город"

    raw = city.strip()
    key = _normalize_city(raw)

    m = re.fullmatch(r"(?:utc|gmt)?\s*([+-]?\d{1,2})", key.replace(" ", ""))
    if key.startswith(("utc", "gmt", "+", "-")) or re.fullmatch(r"[+-]?\d{1,2}", key):
        try:
            off = int(m.group(1) if m else key)
            if -12 <= off <= 14:
                return f"UTC{off:+d}", off, None
        except (ValueError, AttributeError):
            pass

    if key in _CITY_OFFSETS:
        return raw.strip(), _CITY_OFFSETS[key], None

    for name in sorted(_CITY_OFFSETS.keys(), key=len, reverse=True):
        if name in key or key in name:
            return raw.strip(), _CITY_OFFSETS[name], None

    return None, None, (
        f"Город \u00ab{raw}\u00bb не знаю. "
        f"Напиши крупный город рядом "
        f"или офсет UTC+3 / UTC+7."
    )


def parse_briefing_time(value: str) -> tuple[str | None, str | None]:
    if value is None:
        return None, "Укажи время"
    s = str(value).strip().lower().replace(".", ":")
    s = s.replace("часов", "").replace("часа", "").replace("час", "").strip()
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", s)
    if not m:
        return None, "Время в формате HH:MM"
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    if hour > 23 or minute > 59:
        return None, "Часы 0-23, минуты 0-59"
    return f"{hour:02d}:{minute:02d}", None


def default_prefs() -> dict:
    return {
        "city": DEFAULT_CITY,
        "tz_offset_hours": DEFAULT_OFFSET_HOURS,
        "briefing_time": DEFAULT_BRIEFING_TIME,
        "briefing_enabled": True,
    }


def get_user_prefs(user_id: str) -> dict:
    db = get_db()
    row = (
        db.table("users")
        .select("prefs")
        .eq("id", user_id)
        .limit(1)
        .execute()
    ).data
    prefs = (row[0].get("prefs") if row else None) or {}
    if not isinstance(prefs, dict):
        prefs = {}
    base = default_prefs()
    base.update({k: v for k, v in prefs.items() if v is not None})
    try:
        base["tz_offset_hours"] = int(base.get("tz_offset_hours", DEFAULT_OFFSET_HOURS))
    except (TypeError, ValueError):
        base["tz_offset_hours"] = DEFAULT_OFFSET_HOURS
    time_str, _err = parse_briefing_time(str(base.get("briefing_time", DEFAULT_BRIEFING_TIME)))
    base["briefing_time"] = time_str or DEFAULT_BRIEFING_TIME
    base["briefing_enabled"] = bool(base.get("briefing_enabled", True))
    base["city"] = base.get("city") or DEFAULT_CITY
    return base


def user_tz(user_id: str) -> timezone:
    prefs = get_user_prefs(user_id)
    return timezone(timedelta(hours=prefs["tz_offset_hours"]))


def user_now(user_id: str) -> datetime:
    return datetime.now(user_tz(user_id))


def _save_prefs(user_id: str, prefs: dict) -> dict:
    db = get_db()
    row = (
        db.table("users")
        .select("prefs")
        .eq("id", user_id)
        .limit(1)
        .execute()
    ).data
    current = (row[0].get("prefs") if row else None) or {}
    if not isinstance(current, dict):
        current = {}
    current.update(prefs)
    db.table("users").update({"prefs": current}).eq("id", user_id).execute()
    return get_user_prefs(user_id)


def set_briefing_prefs(
    user_id: str,
    city: str | None = None,
    time: str | None = None,
    enabled: bool | None = None,
    utc_offset: int | None = None,
) -> str:
    prefs = get_user_prefs(user_id)
    updates: dict = {}

    if utc_offset is not None:
        try:
            off = int(utc_offset)
        except (TypeError, ValueError):
            return "utc_offset должен быть целым числом часов"
        if not -12 <= off <= 14:
            return "utc_offset вне диапазона -12..+14"
        updates["tz_offset_hours"] = off
        if city:
            updates["city"] = city.strip()
        elif not prefs.get("city") or prefs["city"] == DEFAULT_CITY:
            updates["city"] = f"UTC{off:+d}"

    if city is not None and city.strip():
        display, offset, err = resolve_city(city)
        if err:
            if utc_offset is None:
                return err
            updates["city"] = city.strip()
        else:
            updates["city"] = display
            updates["tz_offset_hours"] = offset

    if time is not None:
        parsed, err = parse_briefing_time(time)
        if err:
            return err
        updates["briefing_time"] = parsed

    if enabled is not None:
        updates["briefing_enabled"] = bool(enabled)

    if not updates:
        return "Нечего менять. Укажи city и/или time."

    result = _save_prefs(user_id, updates)
    off = result["tz_offset_hours"]
    status = "включён" if result["briefing_enabled"] else "выключен"
    return (
        f"Ок. Город: {result['city']} (UTC{off:+d}). "
        f"Утренняя сводка {status}, каждый день в {result['briefing_time']} по местному времени."
    )


def format_briefing_prefs(user_id: str) -> str:
    p = get_user_prefs(user_id)
    off = p["tz_offset_hours"]
    status = "да" if p["briefing_enabled"] else "нет"
    local = user_now(user_id).strftime("%H:%M")
    return (
        f"Город: {p['city']} (UTC{off:+d})\n"
        f"Сводка: {p['briefing_time']} (включён: {status})\n"
        f"Сейчас у тебя: {local}"
    )


def briefing_due(now: datetime, briefing_time: str, *, enabled: bool = True) -> bool:
    """True if local time is at or after today's briefing hour.

    Catch-up after a late tick or container restart. Duplicate sends are
    blocked by `_briefing_already_sent`, not by a 1-minute window.
    """
    if not enabled:
        return False
    parsed, err = parse_briefing_time(str(briefing_time))
    if err or not parsed:
        return False
    hh, mm = map(int, parsed.split(":"))
    return now.hour * 60 + now.minute >= hh * 60 + mm


def should_send_briefing_now(user_id: str) -> bool:
    p = get_user_prefs(user_id)
    return briefing_due(
        user_now(user_id),
        p["briefing_time"],
        enabled=p["briefing_enabled"],
    )
