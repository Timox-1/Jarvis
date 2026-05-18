# Assistant Bot

Личный ИИ-ассистент в Telegram на GPT-4o с браузером и памятью.

## Быстрый старт

1. Скопировать `.env.example` → `.env` и заполнить ключи
2. Применить миграцию: `db/migrations/001_initial.sql` через Supabase Dashboard
3. Запустить локально:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   python -m bot.main
   ```

## Деплой на VPS

```bash
git clone https://github.com/Timox-1/assistant-bot.git
cd assistant-bot
cp .env.example .env && nano .env
docker-compose up -d --build
```

## Обновление

```bash
git pull && docker-compose up -d --build
```

## Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `TELEGRAM_TOKEN` | Токен бота от @BotFather |
| `BOTHUB_API_KEY` | API ключ BotHub |
| `SUPABASE_URL` | URL проекта Supabase |
| `SUPABASE_SERVICE_KEY` | Service role ключ Supabase |
| `ALLOWED_TELEGRAM_IDS` | Telegram ID разрешённых пользователей (через запятую) |
| `ADMIN_TELEGRAM_IDS` | Telegram ID администраторов |
