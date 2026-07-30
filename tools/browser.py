import asyncio
import base64
from playwright.async_api import async_playwright, Page

_browser = None
_page: Page | None = None


async def _get_page() -> Page:
    global _browser, _page
    if _browser is None:
        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
    if _page is None or _page.is_closed():
        _page = await _browser.new_page(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
    return _page


async def _screenshot() -> str:
    page = await _get_page()
    screenshot_bytes = await page.screenshot(full_page=False)
    return base64.b64encode(screenshot_bytes).decode()


async def browser_navigate(url: str) -> dict:
    page = await _get_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
        screenshot_b64 = await _screenshot()
        text = await page.inner_text("body")
        return {
            "status": "ok",
            "url": page.url,
            "screenshot_base64": screenshot_b64,
            "text_preview": text[:2000],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def browser_click(x: int, y: int) -> dict:
    page = await _get_page()
    try:
        await page.mouse.click(x, y)
        await page.wait_for_timeout(1000)
        screenshot_b64 = await _screenshot()
        return {"status": "ok", "screenshot_base64": screenshot_b64}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def browser_type(text: str) -> dict:
    page = await _get_page()
    try:
        await page.keyboard.type(text, delay=50)
        await page.wait_for_timeout(500)
        screenshot_b64 = await _screenshot()
        return {"status": "ok", "screenshot_base64": screenshot_b64}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def browser_press(key: str) -> dict:
    page = await _get_page()
    try:
        await page.keyboard.press(key)
        await page.wait_for_timeout(1000)
        screenshot_b64 = await _screenshot()
        return {"status": "ok", "screenshot_base64": screenshot_b64}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def browser_get_text() -> dict:
    page = await _get_page()
    try:
        text = await page.inner_text("body")
        return {"status": "ok", "text": text[:5000]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def browser_send_screenshot(url: str | None = None) -> dict:
    """Capture current page (optionally after navigating) for delivery to the user."""
    if url:
        nav = await browser_navigate(url)
        if nav["status"] == "error":
            return nav
    elif _page is None or _page.is_closed():
        return {
            "status": "error",
            "error": "Браузер не открыт. Укажи url или сначала вызови browser_navigate.",
        }

    page = await _get_page()
    try:
        screenshot_bytes = await page.screenshot(full_page=False)
        return {"status": "ok", "url": page.url, "screenshot_bytes": screenshot_bytes}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def deliver_screenshot_to_user(
    bot, chat_id: int, screenshot_bytes: bytes, caption: str | None = None,
) -> dict:
    """Send PNG screenshot bytes to the user's Telegram chat."""
    from io import BytesIO
    from telegram import InputFile

    photo = InputFile(BytesIO(screenshot_bytes), filename="screenshot.png")

    try:
        await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
        print(f"[screenshot] sent to chat_id={chat_id} ({len(screenshot_bytes)} bytes)")
        return {"status": "ok"}
    except Exception as e:
        print(f"[screenshot error] chat_id={chat_id}: {e}")
        return {"status": "error", "error": str(e)}


async def browser_close() -> dict:
    global _page
    if _page and not _page.is_closed():
        await _page.close()
        _page = None
    return {"status": "ok"}
