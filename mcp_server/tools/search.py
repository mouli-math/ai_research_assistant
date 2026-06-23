"""Tavily web search tool for the MCP server."""

import logging

from tavily import TavilyClient

from config import config

logger = logging.getLogger(__name__)

# Module-level client — created once and reused across calls
_client = TavilyClient(api_key=config.TAVILY_API_KEY)


def perform_search(query: str, max_results: int = 5) -> dict:
    """Perform a web search via the Tavily API.

    Args:
        query:       The search query string.
        max_results: Maximum number of result items to return.

    Returns:
        Dict with keys:
          - 'query':   the original query
          - 'answer':  Tavily's AI-generated answer summary (may be '')
          - 'results': list of dicts, each with 'title', 'url', 'content'
                       (content truncated to 500 chars)
        On error, 'error' key is added and 'results' is an empty list.
    """
    try:
        logger.info(f"Tavily search: {query!r} (max_results={max_results})")
        response = _client.search(
            query=query,
            max_results=max_results,
            include_answer=True,
        )
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],
            }
            for r in response.get("results", [])
        ]
        logger.info(f"Tavily search returned {len(results)} results")
        return {
            "query": query,
            "answer": response.get("answer", ""),
            "results": results,
        }

    except Exception as exc:
        logger.error(f"Tavily search failed for {query!r}: {exc}")
        return {"query": query, "error": str(exc), "results": []}
