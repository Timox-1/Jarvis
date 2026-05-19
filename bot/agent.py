import json
from openai import AsyncOpenAI
from config import BOTHUB_API_KEY, BOTHUB_BASE_URL, GPT_MODEL
from tools import TOOLS
from tools.memory import save_memory, forget_memory, read_memory
from tools.browser import browser_navigate, browser_click, browser_type, browser_press, browser_get_text
from tools.n8n import call_integration, list_integrations_for_user
from system_prompt import get_system_prompt

client = AsyncOpenAI(api_key=BOTHUB_API_KEY, base_url=BOTHUB_BASE_URL)

MAX_TOOL_ROUNDS = 10


async def _execute_tool(tool_name: str, args: dict, user_id: str) -> str:
    if tool_name == "save_memory":
        return save_memory(user_id, args["key"], args["value"])

    if tool_name == "forget_memory":
        return forget_memory(user_id, args["key"])

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

    if tool_name == "list_integrations":
        result = list_integrations_for_user(user_id)
        return json.dumps(result) if result else "[]"

    if tool_name == "call_integration":
        result = await call_integration(user_id, args["integration_type"], args.get("payload", {}))
        return json.dumps(result)

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


async def run_agent(user_id: str, user_message: str, history: list[dict]) -> str:
    memory = read_memory(user_id)
    integrations = list_integrations_for_user(user_id)
    system_prompt = get_system_prompt(memory, integrations)

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

            tool_result = await _execute_tool(tool_name, args, user_id)

            screenshot_b64 = None
            try:
                parsed = json.loads(tool_result)
                screenshot_b64 = parsed.get("screenshot_base64")
                if screenshot_b64:
                    parsed.pop("screenshot_base64", None)
                    tool_result = json.dumps(parsed)
            except (json.JSONDecodeError, AttributeError):
                pass

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
