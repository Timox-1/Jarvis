import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BOTHUB_API_KEY = os.environ["BOTHUB_API_KEY"]
BOTHUB_BASE_URL = "https://bothub.chat/api/v2/openai/v1"
GPT_MODEL = "gpt-4o"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "assembly-ai-nano")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

ADMIN_TELEGRAM_IDS = [
    int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x
]
ALLOWED_TELEGRAM_IDS = [
    int(x) for x in os.getenv("ALLOWED_TELEGRAM_IDS", "").split(",") if x
]

# Contact shown when access is denied (Telegram @username or text)
ACCESS_CONTACT = os.getenv("ACCESS_CONTACT", "@TimohTG")

# VK community bot (optional — Long Poll starts only if token is set)
VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN", "")
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "")

YANDEX_CALENDAR_CLIENT_ID = os.environ["YANDEX_CALENDAR_CLIENT_ID"]
YANDEX_CALENDAR_CLIENT_SECRET = os.environ["YANDEX_CALENDAR_CLIENT_SECRET"]
