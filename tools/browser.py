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


async def browser_close() -> dict:
    global _page
    if _page and not _page.is_closed():
        await _page.close()
        _page = None
    return {"status": "ok"}
