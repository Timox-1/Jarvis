import asyncio
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


async def _post_init(app):
    asyncio.create_task(_reminder_loop(app.bot))


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
