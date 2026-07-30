# Джарвис — личный ИИ-ассистент в Telegram

Бот на GPT-4o, который не отвечает, а **делает**: ведёт задачи, шлёт напоминания, читает и пишет почту, правит календарь, считает деньги, ходит по сайтам в headless-браузере. Управление — обычным языком, текстом или голосом.

Бот: [@Jarvis_yopta_bot](https://t.me/Jarvis_yopta_bot) · Прод: VPS Timeweb, Docker · Автодеплой: push в `main`

---

## Как это работает

```
Telegram (текст / голос / фото / PDF)
  ↓
bot/handlers.py     проверяет whitelist, транскрибирует голос (Whisper),
                    вытаскивает текст из PDF, грузит историю
  ↓
bot/agent.py        собирает контекст: system prompt + долгая память + 20 последних сообщений
  ↓
GPT-4o (BotHub)     решает: ответить словами или вызвать инструмент
  ↓                 ↑
tools/              39 инструментов: задачи, напоминания, календарь, почта,
                    контакты, рассылки, финансы, браузер, поиск, n8n
  ↓                 └── результат возвращается модели, она думает дальше (до 10 кругов)
  ↓
Telegram            ответ пользователю
  ↓
Supabase            диалог пишется в messages
```

Ключевая деталь: модель сама выбирает инструмент по описанию из `tools/__init__.py`. Никаких команд и кнопок — «закрой задачу про смету» и «отмени встречу с Максимом» разбираются одинаково.

### Память — три уровня

| Уровень | Где живёт | Срок жизни |
|---------|-----------|-----------|
| Short-term | `messages[]` внутри одного вызова `run_agent` | один запрос |
| Mid-term | Supabase `messages` — последние 20 | между запросами |
| Long-term | Supabase `user_memory` — факты о пользователе, попадают в system prompt | вечно |

Долгую память бот пополняет сам: услышал важное — вызвал `save_memory`.

### Фоновые задачи

Обе стартуют в `_post_init` (`bot/main.py`) как asyncio-таски:

- **Напоминания** — раз в 60 секунд проверяет `reminders.fire_at <= now`, пишет в чат, ставит `done`.
- **Утренний брифинг** — в 09:00 по Кемерово шлёт сводку: просроченные задачи, задачи на сегодня, напоминания, встречи из календаря.

---

## Что умеет — 39 инструментов

### Задачи
`add_task` · `list_tasks` · `complete_task` · `delete_task` · `update_task` · `get_today_summary`

Срок, время, приоритет (`low` / `normal` / `high` / `urgent`), статус. Сводка дня = сегодня + просроченное + напоминания.

### Напоминания
`set_reminder` · `list_reminders` · `delete_reminder`

### Календарь (Яндекс, CalDAV)
`list_events` · `create_event` · `delete_event`

Подключение — `/connect_calendar` → OAuth Яндекса → n8n callback → токены в Supabase. Рефреш токена автоматический.

### Почта (Яндекс, IMAP/SMTP)
`list_emails` · `read_email` · `send_email`

Нужен app-password (не обычный пароль) и включённый IMAP в настройках почты.

### Контакты и заметки
`add_contact` · `list_contacts` · `create_contact_group` · `list_contact_groups` · `add_contact_to_group` · `add_contact_note` · `list_contact_notes`

Заметки удобно надиктовывать голосом после звонка — история по контакту копится.

### Рассылки
`prepare_broadcast` · `confirm_broadcast` · `get_broadcast_history`

Два шага: превью получателей → подтверждение. Шлёт только по числовому `telegram_id`; получатель должен был сам написать боту (антиспам Telegram).

### Финансы
`add_expense` · `list_expenses` · `get_expense_summary` · `add_income` · `get_financial_summary`

«Потратил 450 на такси и 1200 в пятёрочке» — разберёт на две траты и разложит по категориям сам. P&L: доходы − расходы за период.

### Браузер (Playwright, headless Chromium)
`browser_navigate` · `browser_click` · `browser_type` · `browser_press` · `browser_get_text`

Видит страницу глазами GPT-4o (скриншот → vision), кликает по координатам. Капча или 2FA — спросит в чате.

### Прочее
`web_search` (DuckDuckGo, без ключа) · `save_memory` · `forget_memory` · `list_integrations` · `call_integration` (произвольный n8n webhook)

**Скриншоты:** `browser_navigate` делает скрин для vision модели; `browser_send_screenshot` отправляет PNG пользователю в Telegram.

### Команды

| Команда | Что делает |
|---------|-----------|
| `/start` | Список возможностей |
| `/status` | Дашборд: задачи, напоминания, статус календаря |
| `/connect_calendar` | OAuth Яндекс Календаря |
| `/clear` | Очистить историю + сбросить браузер |

---

## Инструменты принимают названия, а не только UUID

Неочевидное, но важное решение (`tools/resolve.py`).

Инструменты, меняющие состояние, раньше требовали строгий UUID. Модель этот UUID знать не может — и вместо вызова инструмента она просто **соглашалась на словах**: «Рад, что всё выполнено!». Задача оставалась в базе и каждое утро приходила в брифинге как просроченная.

Теперь `complete_task`, `delete_task`, `update_task`, `delete_reminder`, `add_contact_note`, `delete_event` принимают либо UUID, либо фрагмент названия:

- одно совпадение → выполняет;
- несколько → возвращает список и требует уточнить у пользователя (не угадывает);
- ноль → честно отказывает и предлагает посмотреть список.

Плюс в system prompt зашит запрет подтверждать изменение состояния словами без вызова инструмента.

---

## Стек

- **Python 3.11** (`python:3.11-slim` в Docker)
- **python-telegram-bot** ≥21 — long polling
- **GPT-4o** через [BotHub](https://bothub.chat) (OpenAI-совместимый API) — чат, vision, Whisper
- **Supabase** (PostgreSQL) — вся персистентность
- **Playwright** — headless Chromium
- **caldav** + **icalendar** — Яндекс Календарь
- **PyMuPDF** — текст из PDF
- **n8n Cloud** — OAuth-callback и внешние интеграции
- **Docker Compose** на VPS Timeweb

## Таблицы Supabase

| Таблица | Что хранит |
|---------|-----------|
| `users` | Telegram ID, имя, `is_active`, тариф |
| `messages` | История диалога (роль + текст) |
| `user_memory` | Долгая память: ключ → значение |
| `tasks` | Задачи: срок, приоритет, статус |
| `reminders` | Напоминания: `fire_at`, `done` |
| `contacts`, `contact_groups`, `contact_group_members` | Адресная книга и группы |
| `contact_notes` | Заметки по контактам |
| `broadcasts` | Рассылки: получатели, счётчики, статус |
| `expenses`, `income` | Финансы |
| `integrations` | n8n webhooks (тип → URL) |
| `user_integrations` | OAuth-токены (Яндекс Календарь) |

Все таблицы — с явными `GRANT ... TO service_role, authenticated`. Роли `anon` доступа нет.

---

## Запуск локально

```bash
cp .env.example .env    # заполнить ключи
pip install -r requirements.txt
playwright install chromium
python -m bot.main
```

Миграции применяются через Supabase Dashboard в порядке номеров: `db/migrations/001_initial.sql` → `002_tasks_contacts.sql` → `003_user_integrations.sql`.

## Деплой

Автоматический: push в `main` → GitHub Actions (`.github/workflows/deploy.yml`) заходит на VPS по SSH, делает `git pull`, `docker compose up -d --build` и проверяет, что контейнер поднялся.

> Compose **v2** (`docker compose`, без дефиса). Бинаря `docker-compose` v1 на VPS нет — вызов через дефис молча ронял шаг сборки, и контейнер месяцами крутил старый образ.

Вручную:

```bash
cd /opt/jarvis && git pull origin main && docker compose up -d --build
```

## Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `TELEGRAM_TOKEN` | Токен бота от @BotFather |
| `BOTHUB_API_KEY` | Ключ BotHub (GPT-4o + Whisper) |
| `SUPABASE_URL` | URL проекта Supabase |
| `SUPABASE_SERVICE_KEY` | Service role ключ |
| `ALLOWED_TELEGRAM_IDS` | Whitelist пользователей, через запятую |
| `ADMIN_TELEGRAM_IDS` | Администраторы, через запятую |
| `YANDEX_CALENDAR_CLIENT_ID` | OAuth-приложение Яндекса |
| `YANDEX_CALENDAR_CLIENT_SECRET` | То же, секрет |

Доступ к боту закрыт whitelist'ом: `ALLOWED_TELEGRAM_IDS`. Кто не в списке — получает отказ.
