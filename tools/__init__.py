TOOLS = [
    # --- Web Search ---
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information (weather, news, prices, events, facts). ALWAYS use this for info lookups — do NOT use browser for searches. Returns titles, URLs and snippets instantly without captchas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results (1-10, default 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },

    # --- Memory ---
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a fact about the user to long-term memory. Use when user tells you something important about themselves (name, preferences, contacts, doctor, car, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short identifier, e.g. 'doctor_name', 'car', 'home_address'"},
                    "value": {"type": "string", "description": "The value to remember"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_memory",
            "description": "Remove a fact from long-term memory when user says to forget something",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key to forget"},
                },
                "required": ["key"],
            },
        },
    },

    # --- Tasks/TODO ---
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a task to user's TODO list. Use for any task, meeting prep, follow-up, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title/description"},
                    "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)"},
                    "due_time": {"type": "string", "description": "Due time in HH:MM format (optional)"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "Priority level (default: normal)"
                    },
                    "description": {"type": "string", "description": "Detailed description (optional)"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List user's tasks. Use for 'what do I have today', 'my tasks', 'what's planned'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_filter": {
                        "type": "string",
                        "description": "'today', 'tomorrow', 'week', or specific date YYYY-MM-DD"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "done"],
                        "description": "Filter by status"
                    },
                    "include_completed": {"type": "boolean", "description": "Include completed tasks (default: false)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed. ALWAYS call this when the user says a task is done ('сделано', 'выполнил', 'уже закрыл', 'просроченные выполнены') — never just agree in words.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID, or a fragment of the task title (e.g. 'отчёт Максиму') — the title is matched against the user's open tasks."},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task from the list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID, or a fragment of the task title — the title is matched against the user's open tasks."},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task (change title, deadline, priority, status). Use when user says 'перенеси задачу', 'измени срок', 'повысь приоритет'. First call list_tasks to get task_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID to update"},
                    "title": {"type": "string", "description": "New title (optional)"},
                    "due_date": {"type": "string", "description": "New due date YYYY-MM-DD (optional)"},
                    "due_time": {"type": "string", "description": "New due time HH:MM (optional)"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "New priority (optional)"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "done"],
                        "description": "New status (optional)"
                    },
                    "description": {"type": "string", "description": "New description (optional)"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_summary",
            "description": "Get a summary of today: tasks, overdue items, reminders. Use for 'what's on my plate', 'brief me', 'morning summary'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },

    # --- Contacts ---
    {
        "type": "function",
        "function": {
            "name": "add_contact",
            "description": "Add a contact to the address book. Use when user mentions a new person with details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact's full name"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "email": {"type": "string", "description": "Email address"},
                    "telegram_id": {"type": "integer", "description": "Numeric Telegram user ID (required for broadcasts). Use when user provides a number like 358249169"},
                    "telegram_username": {"type": "string", "description": "Telegram @username without @. Use only if numeric telegram_id is unknown"},
                    "company": {"type": "string", "description": "Company name"},
                    "role": {"type": "string", "description": "Job title/role"},
                    "notes": {"type": "string", "description": "Any notes about the contact"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for grouping, e.g. ['client', 'vip']"
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_contacts",
            "description": "List contacts from address book. Search by name or filter by tag.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Search by name"},
                    "tag": {"type": "string", "description": "Filter by tag"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_contact_group",
            "description": "Create a group for organizing contacts (e.g. 'Clients', 'Team', 'VIP').",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Group name"},
                    "description": {"type": "string", "description": "Group description"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_contact_groups",
            "description": "List all contact groups.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_contact_to_group",
            "description": "Add a contact to a group. Use when user says 'добавь [имя] в группу [название]'. First find contact via list_contacts, find group via list_contact_groups.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact UUID from list_contacts"},
                    "group_id": {"type": "string", "description": "Group UUID from list_contact_groups"},
                },
                "required": ["contact_id", "group_id"],
            },
        },
    },

    # --- Reminders ---
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder for the user. Will send a message at the specified time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Reminder text to send to the user"},
                    "fire_at": {
                        "type": "string",
                        "description": "ISO 8601 datetime with timezone when to fire, e.g. '2026-05-19T15:00:00+03:00' for MSK",
                    },
                },
                "required": ["text", "fire_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all pending (not yet fired) reminders for the user",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_reminder",
            "description": "Cancel and delete a reminder. ALWAYS call this when the user cancels a reminder — never just confirm in words.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "Reminder UUID, or a fragment of its text (e.g. 'позвонить Иванову') — matched against active reminders."},
                },
                "required": ["reminder_id"],
            },
        },
    },

    # --- Browser ---
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Open a URL in the browser and get a screenshot + text. Use to start any web task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL including https://"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click at coordinates (x, y) on the current browser page. Use after seeing a screenshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate to click"},
                    "y": {"type": "integer", "description": "Y coordinate to click"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type text into the currently focused input field in the browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_press",
            "description": "Press a keyboard key in the browser (e.g. 'Enter', 'Tab', 'Escape')",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key name: Enter, Tab, Escape, ArrowDown, etc."},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": "Get the full text content of the current browser page",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # --- Broadcasts ---
    {
        "type": "function",
        "function": {
            "name": "prepare_broadcast",
            "description": "Prepare a broadcast message to multiple contacts. Returns preview of recipients. Use before send_broadcast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message text to send"},
                    "group_id": {"type": "string", "description": "Send to contacts in this group"},
                    "tag": {"type": "string", "description": "Send to contacts with this tag (e.g. 'clients', 'team')"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_broadcast",
            "description": "Confirm and send a prepared broadcast. Call after prepare_broadcast when user confirms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "broadcast_id": {"type": "string", "description": "Broadcast ID from prepare_broadcast. If not known, leave empty — will use the latest pending broadcast"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_broadcast_history",
            "description": "Get history of sent broadcasts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of records (default 10)"},
                },
                "required": [],
            },
        },
    },

    # --- Integrations ---
    {
        "type": "function",
        "function": {
            "name": "list_integrations",
            "description": "Get list of available integrations configured for this user (CRM, calendar, etc.). Call this first before call_integration to see what's available.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_integration",
            "description": "Call an external integration (CRM, calendar, etc.) via n8n webhook. Use list_integrations first to see available types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "integration_type": {
                        "type": "string",
                        "description": "Integration type, e.g. 'amocrm', 'google_calendar', 'bitrix'",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Data to send to the integration",
                    },
                },
                "required": ["integration_type"],
            },
        },
    },

    # --- Яндекс Календарь ---
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "Показать события в Яндекс Календаре за период. Используй когда пользователь спрашивает 'что у меня в календаре', 'какие встречи на неделе' и т.п. Если календарь не подключён — предложи /connect_calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Начало периода в формате YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода в формате YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Создать событие в Яндекс Календаре. Используй когда пользователь говорит 'запиши встречу', 'добавь в календарь'. Если календарь не подключён — предложи /connect_calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Название события"},
                    "start": {"type": "string", "description": "Начало в ISO формате с timezone, напр. 2026-05-22T15:00:00+03:00"},
                    "end": {"type": "string", "description": "Конец в ISO формате с timezone, напр. 2026-05-22T16:00:00+03:00"},
                    "description": {"type": "string", "description": "Описание события (опционально)"},
                },
                "required": ["title", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Удалить событие из Яндекс Календаря. Вызывай всегда, когда пользователь отменяет встречу — не подтверждай отмену на словах.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_uid": {"type": "string", "description": "UID события из list_events, либо название встречи (например 'встреча с Максимом') — ищется среди событий за -7..+90 дней."},
                },
                "required": ["event_uid"],
            },
        },
    },

    # --- Email ---
    {
        "type": "function",
        "function": {
            "name": "list_emails",
            "description": "List recent emails from Yandex Mail. Use when user says 'покажи письма', 'что в почте', 'новые письма'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "IMAP папка, по умолчанию INBOX"},
                    "limit": {"type": "integer", "description": "Количество писем, по умолчанию 10"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read full email body by ID from list_emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID письма из list_emails"},
                    "folder": {"type": "string", "description": "IMAP папка, по умолчанию INBOX"},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send email via Yandex Mail. Use when user says 'напиши письмо', 'отправь email'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Email получателя"},
                    "subject": {"type": "string", "description": "Тема письма"},
                    "body": {"type": "string", "description": "Текст письма"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },

    # --- Contact Notes ---
    {
        "type": "function",
        "function": {
            "name": "add_contact_note",
            "description": "Save a note about a contact after a call or meeting. Use when user says 'запиши по [имя]', 'после звонка с [имя]', 'отметь по контакту'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact UUID, or the contact's name (e.g. 'Максим') — matched against the address book."},
                    "text": {"type": "string", "description": "Текст заметки"},
                },
                "required": ["contact_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_contact_notes",
            "description": "Show notes history for a contact. Use when user asks 'что по [имя]', 'история с [имя]', 'заметки по контакту'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact UUID, or the contact's name (e.g. 'Максим')."},
                },
                "required": ["contact_id"],
            },
        },
    },

    # --- Income ---
    {
        "type": "function",
        "function": {
            "name": "add_income",
            "description": "Record an income entry. Use when user says 'получил оплату', 'пришли деньги', 'доход', 'заработал', 'клиент оплатил'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Сумма в рублях"},
                    "source": {
                        "type": "string",
                        "description": "Источник дохода, напр. 'клиент', 'фриланс', 'бизнес', 'инвестиции', 'прочее'"
                    },
                    "description": {"type": "string", "description": "Описание: от кого, за что"},
                    "income_date": {"type": "string", "description": "Дата YYYY-MM-DD, по умолчанию сегодня"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Get income vs expenses summary (P&L). Use for 'сколько заработал', 'финансовая сводка', 'баланс за месяц', 'прибыль'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "week", "month"],
                        "description": "Период"
                    },
                },
                "required": [],
            },
        },
    },

    # --- Expenses ---
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Record an expense. Use when user says 'потратил', 'заплатил', 'купил за', 'расход'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Сумма в рублях"},
                    "category": {
                        "type": "string",
                        "enum": ["еда", "транспорт", "жильё", "здоровье", "развлечения", "бизнес", "прочее"],
                        "description": "Категория расхода"
                    },
                    "description": {"type": "string", "description": "На что потрачено"},
                    "expense_date": {"type": "string", "description": "Дата YYYY-MM-DD, по умолчанию сегодня"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_expenses",
            "description": "List expenses for a period. Use for 'сколько потратил', 'мои расходы', 'покажи траты'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "week", "month"],
                        "description": "Период"
                    },
                    "category": {"type": "string", "description": "Фильтр по категории"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expense_summary",
            "description": "Get expense totals by category. Use for 'итого', 'сводка расходов', 'на что трачу больше'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "week", "month"],
                        "description": "Период"
                    },
                },
                "required": [],
            },
        },
    },
]
