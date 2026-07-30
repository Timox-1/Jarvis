import asyncio
from datetime import datetime, timezone, timedelta, date
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN, VK_GROUP_TOKEN
from bot.handlers import (
    handle_message,
    handle_document,
    handle_photo,
    handle_voice,
    handle_start,
    handle_clear,
    handle_connect_calendar,
    handle_status,
    handle_invite,
    handle_invite_vk,
    handle_link_vk,
)
from tools.reminders import check_and_fire_reminders
from channels.router import get_router
from channels.telegram import TelegramAdapter

KEMEROVO_TZ = timezone(timedelta(hours=7))


async def _reminder_loop(bot):
    while True:
        await asyncio.sleep(60)
        try:
            await check_and_fire_reminders(bot)
        except Exception as e:
            print(f"Reminder check error: {e}")


BRIEFING_HEADER = "☀️ *Доброе утро! Вот твой день:*"


def _briefing_already_sent(db, user_id: str, since_utc: str) -> bool:
    """Guard against a second briefing after a restart or an early timer wake-up."""
    sent = (db.table("messages")
            .select("id")
            .eq("user_id", user_id)
            .eq("role", "assistant")
            .gte("created_at", since_utc)
            .ilike("content", f"{BRIEFING_HEADER}%")
            .limit(1)
            .execute()).data
    return bool(sent)


async def _send_morning_briefings(_bot=None):
    from db.client import get_db
    from tools.memory import save_message
    from tools.tasks import get_today_summary
    from tools.calendar import list_events
    from channels.router import get_router

    db = get_db()
    users = db.table("users").select("id").eq("is_active", True).execute().data
    router = get_router()

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    kemerovo_now = datetime.now(KEMEROVO_TZ)
    day_start_utc = (kemerovo_now.replace(hour=0, minute=0, second=0, microsecond=0)
                     .astimezone(timezone.utc).isoformat())

    for user in users:
        try:
            if _briefing_already_sent(db, user["id"], day_start_utc):
                continue

            summary = get_today_summary(user["id"])
            lines = [f"{BRIEFING_HEADER}\n"]

            if summary["overdue"]:
                lines.append(f"🔴 *Просроченных задач: {summary['summary']['overdue_count']}*")
                for t in summary["overdue"][:3]:
                    lines.append(f"  • {t['title']} (срок: {t['due_date']})")

            if summary["today"]:
                lines.append(f"\n📋 *Задачи на сегодня:*")
                for t in summary["today"]:
                    lines.append(f"  • {t['title']}")
            else:
                lines.append("\n📋 Задач на сегодня нет.")

            if summary["reminders_today"]:
                lines.append(f"\n⏰ *Напоминания сегодня: {summary['summary']['reminders_count']}*")

            try:
                events = list_events(user["id"], today, tomorrow)
                if events:
                    lines.append(f"\n📅 *Встречи сегодня:*")
                    for e in events[:5]:
                        lines.append(f"  • {e.get('title', 'Без названия')} в {e.get('start', '')[:16]}")
            except Exception:
                pass

            text = "\n".join(lines)
            sent = await router.send_text_to_user(user["id"], text, parse_mode="Markdown")
            if not sent:
                # fallback plain text if markdown failed on all channels
                await router.send_text_to_user(user["id"], text.replace("*", ""))
            save_message(user["id"], "assistant", text)
        except Exception as e:
            print(f"Morning briefing error for user {user['id']}: {e}")


async def _morning_briefing_loop(bot):
    """Sends morning briefing at 09:00 Kemerovo time every day."""
    TARGET_HOUR = 9

    while True:
        now = datetime.now(KEMEROVO_TZ)
        next_run = now.replace(hour=TARGET_HOUR, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)

        while datetime.now(KEMEROVO_TZ) < next_run:
            await asyncio.sleep((next_run - datetime.now(KEMEROVO_TZ)).total_seconds())

        try:
            await _send_morning_briefings(bot)
        except Exception as e:
            print(f"Morning briefing loop error: {e}")


async def _post_init(app):
    get_router().register(TelegramAdapter(app.bot))
    asyncio.create_task(_reminder_loop(app.bot))
    asyncio.create_task(_morning_briefing_loop(app.bot))

    if VK_GROUP_TOKEN:
        asyncio.create_task(_run_vk_safe())
        print("[vk] Long Poll task scheduled")
    else:
        print("[vk] VK_GROUP_TOKEN empty — VK disabled")

    commands = [
        ("start", "Список возможностей"),
        ("status", "Быстрый дашборд — задачи, напоминания"),
        ("connect_calendar", "Подключить Яндекс Календарь"),
        ("clear", "Очистить историю диалога"),
        ("invite", "Админ: выдать доступ TG"),
        ("invite_vk", "Админ: выдать доступ VK"),
        ("link_vk", "Админ: связать TG+VK"),
    ]
    await app.bot.set_my_commands(commands)


async def _run_vk_safe():
    try:
        from channels.vk import run_vk_bot
        await run_vk_bot()
    except Exception as e:
        print(f"[vk] Long Poll crashed: {e}")


def main() -> None:
    app = (ApplicationBuilder()
           .token(TELEGRAM_TOKEN)
           .post_init(_post_init)
           .build())

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("clear", handle_clear))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("connect_calendar", handle_connect_calendar))
    app.add_handler(CommandHandler("invite", handle_invite))
    app.add_handler(CommandHandler("invite_vk", handle_invite_vk))
    app.add_handler(CommandHandler("link_vk", handle_link_vk))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
