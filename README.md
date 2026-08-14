# Джарвис — личный ИИ-ассистент в Telegram

Бот на GPT (сейчас `gpt-4.1-mini` через BotHub; vision/Whisper отдельно), который не отвечает, а **делает**: ведёт задачи и проекты, шлёт напоминания, читает и пишет почту, правит календарь, считает деньги, ходит по сайтам в headless-браузере. Управление — обычным языком, текстом или голосом. Multi-user: инвайты, Telegram + VK.

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
GPT (BotHub)        решает: ответить словами или вызвать инструмент
  ↓                 ↑
tools/              52 инструмента: задачи, проекты, напоминания, календарь, почта,
                    контакты, рассылки, финансы, браузер, поиск, n8n, prefs
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
- **Утренний брифинг** — в локальный час юзера (`prefs`), не общий слот 09:00. Если контейнер проснулся позже — догонит, пока за день ещё не слали.

---

## Что умеет — 52 инструмента

### Проекты (dump-and-sort)
`create_project` · `list_projects` · `set_active_project` · `clear_active_project` · `archive_project` · `rename_project` · `add_project_note` · `list_project_notes` · `get_project_summary`

Универсальный контейнер (клиент / сделка / объект). Создал проект → кидаешь сырую инфу → агент раскладывает по задачам, расходам, контактам, напоминаниям и пишет в лог заметок проекта. Активный проект подмешивается в system prompt. Создание проекта нельзя «подтвердить словами» без вызова `create_project`.

### Задачи
`add_task` · `list_tasks` · `complete_task` · `delete_task` · `update_task` · `get_today_summary`

Срок, время, приоритет (`low` / `normal` / `high` / `urgent`), статус, опционально привязка к проекту. Сводка дня = сегодня + просроченное + напоминания.

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
`browser_navigate` · `browser_click` · `browser_type` · `browser_press` · `browser_get_text` · `browser_send_screenshot`

Видит страницу через vision (скриншот → модель), кликает по координатам. Капча или 2FA — спросит в чате. `browser_send_screenshot` шлёт PNG в чат; если в сообщении есть «скрин», фото уходит и после обычного `browser_navigate`.

### Утренний брифинг (prefs)
`set_briefing_prefs` · `get_briefing_prefs`

Время сводки и таймзона на пользователя (не только «09:00 Кемерово на всех»). Если бот проснулся позже часа сводки — догонит, пока за этот день ещё не слали.

### Прочее
`web_search` (DuckDuckGo, без ключа) · `save_memory` · `forget_memory` · `list_integrations` · `call_integration` (произвольный n8n webhook)

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

Промпт этого не гарантирует: модель всё равно иногда пишет «готово», не вызвав тул. Тогда `action_guard` делает один повтор с пинком «вызови инструмент»; если снова мимо — алерт админу, а не тихий фейл до следующей утренней сводки. `archive_project` закрывает открытые задачи проекта, чтобы они не возвращались в брифинге.

---

## Стек

- **Python 3.11** (`python:3.11-slim` в Docker)
- **python-telegram-bot** ≥21 — long polling
- **GPT через [BotHub](https://bothub.chat)** (OpenAI-совместимый API) — чат (`gpt-4.1-mini`), vision, Whisper/AssemblyAI для голоса
- **Supabase** (PostgreSQL) — вся персистентность
- **Playwright** — headless Chromium
- **caldav** + **icalendar** — Яндекс Календарь
- **PyMuPDF** — текст из PDF
- **n8n Cloud** — OAuth-callback и внешние интеграции
- **Docker Compose** на VPS Timeweb

## Таблицы Supabase

| Таблица | Что хранит |
|---------|-----------|
| `users` | Имя, `is_active`, `plan`, `paid_until`, legacy `telegram_id` |
| `user_identities` | Каналы: `telegram` / `vk` + external_id |
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
| `ALLOWED_TELEGRAM_IDS` | Суперадмин whitelist (через запятую) |
| `ADMIN_TELEGRAM_IDS` | Админы: `/invite`, `/invite_vk`, `/link_vk` |
| `ACCESS_CONTACT` | Куда писать при отказе в доступе (напр. `@TimohTG`) |
| `VK_GROUP_TOKEN` | Опционально: токен сообщества VK |
| `VK_GROUP_ID` | Опционально: ID сообщества VK |
| `YANDEX_CALENDAR_CLIENT_ID` | OAuth-приложение Яндекса |
| `YANDEX_CALENDAR_CLIENT_SECRET` | То же, секрет |

Доступ: админ-инвайт (`/invite <telegram_id> [plan] [YYYY-MM-DD]`) или суперадмин из whitelist. Новые без инвайта — отказ.
