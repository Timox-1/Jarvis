import json
import base64
from openai import AsyncOpenAI
from config import BOTHUB_API_KEY, BOTHUB_BASE_URL, GPT_MODEL
from tools import TOOLS
from tools.memory import save_memory, forget_memory, read_memory
from tools.browser import (
    browser_navigate, browser_click, browser_type, browser_press, browser_get_text,
    browser_send_screenshot, deliver_screenshot_to_user,
)
from tools.n8n import call_integration, list_integrations_for_user
from tools.reminders import set_reminder, list_reminders, delete_reminder
from tools.search import web_search
from tools.tasks import add_task, list_tasks, complete_task, delete_task, get_today_summary, update_task
from tools.contacts import (
    add_contact, list_contacts, get_contact, update_contact, delete_contact,
    create_contact_group, list_contact_groups, add_contact_to_group, get_group_contacts
)
from tools.broadcast import prepare_broadcast, confirm_broadcast, get_broadcast_history
from tools.calendar import list_events, create_event, delete_event
from tools.expenses import add_expense, list_expenses, get_expense_summary
from tools.income import add_income, list_income, get_financial_summary
from tools.contact_notes import add_contact_note, list_contact_notes
from tools.email import list_emails, read_email, send_email
from tools.projects import (
    create_project,
    list_projects,
    set_active_project,
    clear_active_project,
    archive_project,
    rename_project,
    add_project_note,
    list_project_notes,
    get_project_summary,
    get_active_project,
    list_projects_preview,
    resolve_project,
)
from system_prompt import get_system_prompt

client = AsyncOpenAI(api_key=BOTHUB_API_KEY, base_url=BOTHUB_BASE_URL)

MAX_TOOL_ROUNDS = 10


def _user_wants_screenshot(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("скрин", "screenshot", "screen shot", "скриншот"))


def _resolve_project_id(user_id: str, args: dict, *, required: bool = False) -> tuple[str | None, str | None]:
    """Resolve optional/required project ref → id. Uses active project when ref omitted."""
    ref = args.get("project")
    if not ref and not required:
        active = get_active_project(user_id)
        return (active["id"] if active else None), None
    proj, error = resolve_project(user_id, ref, allow_active=True)
    if error:
        return None, error
    return proj["id"], None


async def _execute_tool(tool_name: str, args: dict, user_id: str, delivery=None) -> str:
    # --- Memory ---
    if tool_name == "save_memory":
        return save_memory(user_id, args["key"], args["value"])

    if tool_name == "forget_memory":
        return forget_memory(user_id, args["key"])

    # --- Reminders ---
    if tool_name == "set_reminder":
        project_id, err = _resolve_project_id(user_id, args)
        if err and args.get("project"):
            return err
        return set_reminder(user_id, args["text"], args["fire_at"], project_id=project_id)

    if tool_name == "list_reminders":
        result = list_reminders(user_id)
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "delete_reminder":
        return delete_reminder(user_id, args["reminder_id"])

    # --- Tasks ---
    if tool_name == "add_task":
        project_id, err = _resolve_project_id(user_id, args)
        if err and args.get("project"):
            return err
        return add_task(
            user_id,
            args["title"],
            description=args.get("description"),
            due_date=args.get("due_date"),
            due_time=args.get("due_time"),
            priority=args.get("priority", "normal"),
            project_id=project_id,
        )

    if tool_name == "list_tasks":
        project_id = None
        if args.get("project"):
            project_id, err = _resolve_project_id(user_id, args)
            if err:
                return err
        result = list_tasks(
            user_id,
            status=args.get("status"),
            date_filter=args.get("date_filter"),
            include_completed=args.get("include_completed", False),
            project_id=project_id,
        )
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "complete_task":
        return complete_task(user_id, args["task_id"])

    if tool_name == "delete_task":
        return delete_task(user_id, args["task_id"])

    if tool_name == "update_task":
        return update_task(
            user_id,
            args["task_id"],
            title=args.get("title"),
            description=args.get("description"),
            due_date=args.get("due_date"),
            due_time=args.get("due_time"),
            priority=args.get("priority"),
            status=args.get("status"),
        )

    if tool_name == "get_today_summary":
        result = get_today_summary(user_id)
        return json.dumps(result, ensure_ascii=False)

    # --- Contacts ---
    if tool_name == "add_contact":
        project_id, err = _resolve_project_id(user_id, args)
        if err and args.get("project"):
            return err
        return add_contact(
            user_id,
            args["name"],
            phone=args.get("phone"),
            email=args.get("email"),
            telegram_username=args.get("telegram_username"),
            telegram_id=args.get("telegram_id"),
            company=args.get("company"),
            role=args.get("role"),
            notes=args.get("notes"),
            tags=args.get("tags"),
            project_id=project_id,
        )

    if tool_name == "list_contacts":
        result = list_contacts(
            user_id,
            search=args.get("search"),
            tag=args.get("tag")
        )
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "create_contact_group":
        return create_contact_group(
            user_id,
            args["name"],
            description=args.get("description")
        )

    if tool_name == "list_contact_groups":
        result = list_contact_groups(user_id)
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "add_contact_to_group":
        return add_contact_to_group(user_id, args["contact_id"], args["group_id"])

    # --- Broadcasts ---
    if tool_name == "prepare_broadcast":
        result = prepare_broadcast(
            user_id,
            args["message"],
            group_id=args.get("group_id"),
            tag=args.get("tag")
        )
        return json.dumps(result, ensure_ascii=False)

    if tool_name == "confirm_broadcast":
        from channels.router import get_router
        tg = get_router().get("telegram")
        if not tg or not getattr(tg, "bot", None):
            return json.dumps({"status": "error", "error": "Telegram bot not available for broadcast"})
        result = await confirm_broadcast(tg.bot, user_id, args.get("broadcast_id"))
        return json.dumps(result, ensure_ascii=False)

    if tool_name == "get_broadcast_history":
        result = get_broadcast_history(user_id, args.get("limit", 10))
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    # --- Calendar ---
    if tool_name == "list_events":
        try:
            result = list_events(user_id, args["start_date"], args["end_date"])
            return json.dumps(result, ensure_ascii=False)
        except ValueError as e:
            return str(e)

    if tool_name == "create_event":
        try:
            return create_event(
                user_id,
                args["title"],
                args["start"],
                args["end"],
                description=args.get("description", "")
            )
        except ValueError as e:
            return str(e)

    if tool_name == "delete_event":
        try:
            return delete_event(user_id, args["event_uid"])
        except ValueError as e:
            return str(e)

    # --- Email ---
    if tool_name == "list_emails":
        try:
            result = list_emails(user_id, folder=args.get("folder", "INBOX"), limit=args.get("limit", 10))
            return json.dumps(result, ensure_ascii=False)
        except ValueError as e:
            return str(e)

    if tool_name == "read_email":
        try:
            result = read_email(user_id, args["email_id"], folder=args.get("folder", "INBOX"))
            return json.dumps(result, ensure_ascii=False)
        except ValueError as e:
            return str(e)

    if tool_name == "send_email":
        try:
            return send_email(user_id, args["to"], args["subject"], args["body"])
        except ValueError as e:
            return str(e)

    # --- Contact Notes ---
    if tool_name == "add_contact_note":
        return add_contact_note(user_id, args["contact_id"], args["text"])

    if tool_name == "list_contact_notes":
        result = list_contact_notes(user_id, args["contact_id"])
        if isinstance(result, str):  # resolution failed — pass the hint back to GPT
            return result
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    # --- Income ---
    if tool_name == "add_income":
        return add_income(
            user_id,
            args["amount"],
            source=args.get("source", "прочее"),
            description=args.get("description"),
            income_date=args.get("income_date"),
        )

    if tool_name == "get_financial_summary":
        result = get_financial_summary(user_id, period=args.get("period", "month"))
        return json.dumps(result, ensure_ascii=False)

    # --- Expenses ---
    if tool_name == "add_expense":
        project_id, err = _resolve_project_id(user_id, args)
        if err and args.get("project"):
            return err
        return add_expense(
            user_id,
            args["amount"],
            category=args.get("category", "прочее"),
            description=args.get("description"),
            expense_date=args.get("expense_date"),
            project_id=project_id,
        )

    if tool_name == "list_expenses":
        project_id = None
        if args.get("project"):
            project_id, err = _resolve_project_id(user_id, args)
            if err:
                return err
        result = list_expenses(
            user_id,
            period=args.get("period", "week"),
            category=args.get("category"),
            project_id=project_id,
        )
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "get_expense_summary":
        project_id = None
        if args.get("project"):
            project_id, err = _resolve_project_id(user_id, args)
            if err:
                return err
        result = get_expense_summary(
            user_id,
            period=args.get("period", "month"),
            project_id=project_id,
        )
        return json.dumps(result, ensure_ascii=False)

    # --- Projects ---
    if tool_name == "create_project":
        return create_project(
            user_id,
            args["name"],
            description=args.get("description"),
            set_active=args.get("set_active", True),
        )

    if tool_name == "list_projects":
        result = list_projects(user_id, status=args.get("status", "active"))
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "set_active_project":
        return set_active_project(user_id, args["project"])

    if tool_name == "clear_active_project":
        return clear_active_project(user_id)

    if tool_name == "archive_project":
        return archive_project(user_id, args.get("project"))

    if tool_name == "rename_project":
        return rename_project(user_id, args["project"], args["new_name"])

    if tool_name == "add_project_note":
        return add_project_note(
            user_id,
            args["text"],
            project=args.get("project"),
            source="user_dump",
        )

    if tool_name == "list_project_notes":
        result = list_project_notes(
            user_id,
            project=args.get("project"),
            limit=args.get("limit", 20),
        )
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False) if result else "[]"

    if tool_name == "get_project_summary":
        result = get_project_summary(user_id, project=args.get("project"))
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    # --- Browser ---
    if tool_name == "browser_navigate":
        result = await browser_navigate(args["url"])
        if result["status"] == "error":
            return f"Browser error: {result['error']}"
        return json.dumps({
            "url": result["url"],
            "text_preview": result["text_preview"],
            "screenshot_base64": result["screenshot_base64"],
        })

    if tool_name == "browser_click":
        result = await browser_click(args["x"], args["y"])
        if result["status"] == "error":
            return f"Click error: {result['error']}"
        return json.dumps({"screenshot_base64": result["screenshot_base64"]})

    if tool_name == "browser_type":
        result = await browser_type(args["text"])
        if result["status"] == "error":
            return f"Type error: {result['error']}"
        return json.dumps({"screenshot_base64": result["screenshot_base64"]})

    if tool_name == "browser_press":
        result = await browser_press(args["key"])
        if result["status"] == "error":
            return f"Press error: {result['error']}"
        return json.dumps({"screenshot_base64": result["screenshot_base64"]})

    if tool_name == "browser_get_text":
        result = await browser_get_text()
        if result["status"] == "error":
            return f"Get text error: {result['error']}"
        return result["text"]

    if tool_name == "browser_send_screenshot":
        result = await browser_send_screenshot(args.get("url"))
        if result["status"] == "error":
            return f"Screenshot error: {result['error']}"
        return json.dumps({
            "status": "ok",
            "url": result["url"],
            "screenshot_base64": base64.b64encode(result["screenshot_bytes"]).decode(),
            "deliver_to_user": True,
            "caption": args.get("caption"),
        }, ensure_ascii=False)

    # --- Integrations ---
    if tool_name == "list_integrations":
        result = list_integrations_for_user(user_id)
        return json.dumps(result) if result else "[]"

    if tool_name == "call_integration":
        result = await call_integration(user_id, args["integration_type"], args.get("payload", {}))
        return json.dumps(result)

    # --- Search ---
    if tool_name == "web_search":
        result = await web_search(args["query"], args.get("count", 5))
        return json.dumps(result, ensure_ascii=False)

    return f"Unknown tool: {tool_name}"


def _make_vision_message(role: str, content: str, screenshot_b64: str | None = None) -> dict:
    if screenshot_b64:
        return {
            "role": role,
            "content": [
                {"type": "text", "text": content},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                },
            ],
        }
    return {"role": role, "content": content}


async def run_agent(user_id: str, user_message: str, history: list[dict], delivery=None) -> str:
    memory = read_memory(user_id)
    integrations = list_integrations_for_user(user_id)
    active_project = get_active_project(user_id)
    projects_preview = list_projects_preview(user_id)
    system_prompt = get_system_prompt(
        memory,
        integrations,
        active_project=active_project,
        projects_preview=projects_preview,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2000,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        messages.append(msg)

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            tool_result = await _execute_tool(tool_name, args, user_id, delivery)

            screenshot_b64 = None
            deliver_to_user = False
            photo_caption = None
            try:
                parsed = json.loads(tool_result)
                screenshot_b64 = parsed.get("screenshot_base64")
                deliver_to_user = parsed.get("deliver_to_user") or (
                    bool(screenshot_b64) and _user_wants_screenshot(user_message)
                )
                photo_caption = parsed.get("caption")
                if screenshot_b64:
                    parsed.pop("screenshot_base64", None)
                    parsed.pop("deliver_to_user", None)
                    parsed.pop("caption", None)
                    tool_result = json.dumps(parsed, ensure_ascii=False)
            except (json.JSONDecodeError, AttributeError):
                pass

            if screenshot_b64 and deliver_to_user and delivery:
                send_result = await deliver_screenshot_to_user(
                    delivery.channel,
                    delivery.external_id,
                    base64.b64decode(screenshot_b64),
                    photo_caption,
                )
                if send_result["status"] == "error":
                    tool_result = f"Send error: {send_result['error']}"
                else:
                    try:
                        parsed_out = json.loads(tool_result)
                        parsed_out["photo_sent"] = True
                        tool_result = json.dumps(parsed_out, ensure_ascii=False)
                    except json.JSONDecodeError:
                        tool_result = f"{tool_result} [photo_sent: true]"

            messages.append({
                "role": "tool",
                "content": tool_result,
                "tool_call_id": tool_call.id,
            })

            if screenshot_b64:
                messages.append(_make_vision_message(
                    "user",
                    "Вот скриншот текущего состояния браузера:",
                    screenshot_b64,
                ))

    return "Достигнут лимит шагов. Задача не завершена."
