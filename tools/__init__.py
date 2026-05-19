TOOLS = [
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
            "description": "Cancel and delete a reminder by its ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "UUID of the reminder to delete"},
                },
                "required": ["reminder_id"],
            },
        },
    },
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
]
