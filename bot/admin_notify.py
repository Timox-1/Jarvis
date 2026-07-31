"""Push short alerts to admin Telegram accounts (same Jarvis bot)."""

from __future__ import annotations

import logging
import time

from config import ADMIN_TELEGRAM_IDS, ALLOWED_TELEGRAM_IDS

logger = logging.getLogger(__name__)

# Avoid spam if someone hammers the bot while denied
_DENY_COOLDOWN_SEC = 6 * 3600
_last_denied_at: dict[str, float] = {}


def admin_telegram_ids() -> list[int]:
    return sorted({*ADMIN_TELEGRAM_IDS, *ALLOWED_TELEGRAM_IDS})


async def notify_admins(
    text: str,
    *,
    bot=None,
    exclude_telegram_id: int | None = None,
) -> None:
    """Send plain text to all admin TG ids via ChannelRouter or raw Bot."""
    ids = [
        tid for tid in admin_telegram_ids()
        if exclude_telegram_id is None or tid != exclude_telegram_id
    ]
    if not ids:
        return

    sent = False
    try:
        from channels.router import get_router
        tg = get_router().get("telegram")
        if tg is not None:
            for tid in ids:
                try:
                    await tg.send_text(str(tid), text)
                    sent = True
                except Exception as e:
                    logger.warning("admin notify failed tid=%s: %s", tid, e)
            if sent:
                return
    except Exception as e:
        logger.warning("admin notify via router failed: %s", e)

    if bot is None:
        return
    for tid in ids:
        try:
            await bot.send_message(chat_id=tid, text=text)
        except Exception as e:
            logger.warning("admin notify via bot failed tid=%s: %s", tid, e)


async def notify_access_denied(
    *,
    channel: str,
    external_id: str | int,
    name: str | None = None,
    username: str | None = None,
    via: str = "message",
    bot=None,
) -> None:
    """Alert admins that someone hit a closed door."""
    key = f"{channel}:{external_id}"
    now = time.time()
    if via != "start":
        last = _last_denied_at.get(key, 0.0)
        if now - last < _DENY_COOLDOWN_SEC:
            return
    _last_denied_at[key] = now

    uname = f" @{username.lstrip('@')}" if username else ""
    if channel == "telegram":
        invite_hint = f"/invite {external_id} friend"
    else:
        invite_hint = f"/invite_vk {external_id} friend"

    text = (
        f"🚫 Доступ закрыт ({via})\n"
        f"канал: {channel}\n"
        f"id: {external_id}{uname}\n"
        f"имя: {name or '—'}\n"
        f"Инвайт: {invite_hint}"
    )
    await notify_admins(text, bot=bot)


async def notify_invite_done(
    *,
    channel: str,
    external_id: str | int,
    plan: str,
    paid_until: str | None,
    created: bool,
    user_id: str,
    by_admin_telegram_id: int | None = None,
    bot=None,
) -> None:
    action = "создан" if created else "активирован"
    text = (
        f"✅ Инвайт: пользователь {action}\n"
        f"канал: {channel}\n"
        f"id: {external_id}\n"
        f"plan: {plan}\n"
        f"paid_until: {paid_until or '—'}\n"
        f"user_id: {user_id}"
    )
    # Inviter already got the command reply — ping other admin chats too
    await notify_admins(
        text,
        bot=bot,
        exclude_telegram_id=by_admin_telegram_id,
    )
