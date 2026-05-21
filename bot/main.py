import asyncio
from datetime import datetime, timezone, timedelta, date
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN
from bot.handlers import handle_message, handle_document, handle_photo, handle_voice, handle_start, handle_clear, handle_connect_calendar
from tools.reminders import check_and_fire_reminders


async def _reminder_loop(bot):
    while True:
        await asyncio.sleep(60)
        try:
            await check_and_fire_reminders(bot)
        except Exception as e:
            print(f"Reminder check error: {e}")


async def _send_morning_briefings(bot):
    from db.client import get_db
    from tools.tasks import get_today_summary
    from tools.calendar import list_events

    db = get_db()
    users = db.table("users").select("id, telegram_id").eq("is_active", True).execute().data

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    for user in users:
        try:
            summary = get_today_summary(user["id"])
            lines = ["☀️ *Доброе утро! Вот твой день:*\n"]

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
                pass  # No calendar integration — skip silently

            text = "\n".join(lines)
            await bot.send_message(
                chat_id=user["telegram_id"],
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Morning briefing error for user {user['id']}: {e}")


async def _morning_briefing_loop(bot):
    """Sends morning briefing at 09:00 Kemerovo time (02:00 UTC) every day."""
    KEMEROVO_TZ = timezone(timedelta(hours=7))
    TARGET_HOUR = 9

    while True:
        now = datetime.now(KEMEROVO_TZ)
        next_run = now.replace(hour=TARGET_HOUR, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())

        try:
            await _send_morning_briefings(bot)
        except Exception as e:
            print(f"Morning briefing loop error: {e}")


async def _post_init(app):
    asyncio.create_task(_reminder_loop(app.bot))
    asyncio.create_task(_morning_briefing_loop(app.bot))


def main() -> None:
    app = (ApplicationBuilder()
           .token(TELEGRAM_TOKEN)
           .post_init(_post_init)
           .build())

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("clear", handle_clear))
    app.add_handler(CommandHandler("connect_calendar", handle_connect_calendar))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
