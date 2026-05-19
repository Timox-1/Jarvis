from datetime import datetime, timezone, timedelta

MOSCOW_TZ = timezone(timedelta(hours=3))


def get_system_prompt(user_memory: dict, integrations: list = None) -> str:
    memory_text = ""
    if user_memory:
        memory_lines = [f"- {k}: {v}" for k, v in user_memory.items()]
        memory_text = "Что ты знаешь о пользователе:\n" + "\n".join(memory_lines)
    else:
        memory_text = "О пользователе пока ничего не известно."

    now = datetime.now(MOSCOW_TZ).strftime("%A, %d %B %Y, %H:%M (MSK, UTC+3)")

    if integrations:
        integration_lines = [f"- {i['type']}: {i.get('config', {}).get('description', '')}" for i in integrations]
        integrations_text = "Доступные интеграции (вызывай через call_integration):\n" + "\n".join(integration_lines)
    else:
        integrations_text = ""

    return f"""Ты личный ИИ-ассистент. Сейчас: {now}.

{memory_text}

{integrations_text}

Правила:
- Общайся на языке пользователя (русский по умолчанию)
- Запоминай важные факты о пользователе через save_memory
- Для задач в браузере: открой страницу, посмотри скриншот, действуй шаг за шагом
- Если нужна помощь пользователя (капча, СМС-код) — спроси напрямую
- Если задача займёт время — сообщи "Работаю..." в начале
- После браузерной задачи всегда закрывай сессию если она не нужна дальше
- Будь краток в ответах, не пиши лишнего
- При ошибке — объясни что пошло не так и предложи что делать
- Для задач с интеграциями: сразу вызывай call_integration с нужным типом из списка выше, не уточняй лишнего
- Если интеграция вернула поле result — покажи его пользователю полностью
- Для напоминаний: используй fire_at в формате ISO 8601 с MSK-смещением (+03:00), рассчитывай от текущего времени из system prompt"""
