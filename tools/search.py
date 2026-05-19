"""
Web search tool using Brave Search API.
Provides search results without loading full pages — faster and safer than browser.
"""

import httpx
from config import BRAVE_API_KEY

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


async def web_search(query: str, count: int = 5) -> dict:
    """
    Search the web using Brave Search API.
    Returns top results with title, URL, and description snippet.

    Args:
        query: Search query string
        count: Number of results to return (1-10)

    Returns:
        dict with status and results list
    """
    if not BRAVE_API_KEY:
        return {
            "status": "error",
            "error": "BRAVE_API_KEY not configured",
        }

    count = max(1, min(10, count))

    headers = {
        "X-Subscription-Token": BRAVE_API_KEY,
        "Accept": "application/json",
    }

    params = {
        "q": query,
        "count": count,
        "search_lang": "ru",
        "country": "ru",
        "safesearch": "moderate",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                BRAVE_SEARCH_URL,
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        web_results = data.get("web", {}).get("results", [])

        for item in web_results[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            })

        return {
            "status": "ok",
            "query": query,
            "results": results,
        }

    except httpx.TimeoutException:
        return {"status": "error", "error": "Search request timed out"}
    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"HTTP error: {e.response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
