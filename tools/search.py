"""
Web search tool using DuckDuckGo.
Free, no API key required, no registration needed.
"""

import httpx

DDG_URL = "https://api.duckduckgo.com/"


async def web_search(query: str, count: int = 5) -> dict:
    """
    Search the web using DuckDuckGo Instant Answer API + HTML search.
    Returns top results with title, URL, and description snippet.

    Args:
        query: Search query string
        count: Number of results to return (1-10)

    Returns:
        dict with status and results list
    """
    count = max(1, min(10, count))

    # Use DuckDuckGo HTML search (more reliable than API for web results)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # DuckDuckGo HTML search
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
            )
            response.raise_for_status()
            html = response.text

        # Parse results from HTML (simple extraction)
        results = []

        # Find result blocks
        import re

        # Extract result links and snippets
        # Pattern for result entries
        result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
        snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]*</[^>]+>)*[^<]*)</a>'

        links = re.findall(result_pattern, html)
        snippets = re.findall(snippet_pattern, html)

        for i, (url, title) in enumerate(links[:count]):
            # Clean up the URL (DuckDuckGo wraps URLs)
            if "uddg=" in url:
                url_match = re.search(r'uddg=([^&]+)', url)
                if url_match:
                    from urllib.parse import unquote
                    url = unquote(url_match.group(1))

            snippet = ""
            if i < len(snippets):
                # Clean HTML tags from snippet
                snippet = re.sub(r'<[^>]+>', '', snippets[i])

            results.append({
                "title": title.strip(),
                "url": url,
                "description": snippet.strip()[:300],
            })

        if not results:
            return {
                "status": "ok",
                "query": query,
                "results": [],
                "message": "No results found",
            }

        return {
            "status": "ok",
            "query": query,
            "results": results,
        }

    except httpx.TimeoutException:
        return {"status": "error", "error": "Search request timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
