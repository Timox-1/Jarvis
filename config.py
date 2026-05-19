import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BOTHUB_API_KEY = os.environ["BOTHUB_API_KEY"]
BOTHUB_BASE_URL = "https://bothub.chat/api/v2/openai/v1"
GPT_MODEL = "gpt-4o"

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# Brave Search API (free tier: 2000 requests/month)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

ADMIN_TELEGRAM_IDS = [
    int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x
]
ALLOWED_TELEGRAM_IDS = [
    int(x) for x in os.getenv("ALLOWED_TELEGRAM_IDS", "").split(",") if x
]
