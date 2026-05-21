import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BOTHUB_API_KEY = os.environ["BOTHUB_API_KEY"]
BOTHUB_BASE_URL = "https://bothub.chat/api/v2/openai/v1"
GPT_MODEL = "gpt-4o"

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

ADMIN_TELEGRAM_IDS = [
    int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x
]
ALLOWED_TELEGRAM_IDS = [
    int(x) for x in os.getenv("ALLOWED_TELEGRAM_IDS", "").split(",") if x
]

YANDEX_CALENDAR_CLIENT_ID = os.environ["YANDEX_CALENDAR_CLIENT_ID"]
YANDEX_CALENDAR_CLIENT_SECRET = os.environ["YANDEX_CALENDAR_CLIENT_SECRET"]
