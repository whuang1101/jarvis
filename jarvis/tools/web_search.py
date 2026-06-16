from __future__ import annotations

from typing import Any

from .base import BaseTool

_MAX_RESULTS = 10


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web using DuckDuckGo. Returns titles, URLs, and snippets. "
        "Use web_extract on a result URL to get the full page content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (max 10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        query: str = args["query"]
        num: int = min(int(args.get("num_results", 5)), _MAX_RESULTS)
        try:
            from ddgs import DDGS
        except ImportError:
            return "Error: ddgs not installed. Run: pip install ddgs"

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num))
        except Exception as e:
            return f"Search error: {e}"

        if not results:
            return f"No results found for '{query}'"

        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '(no title)')}")
            lines.append(f"   {r.get('href', '')}")
            if r.get("body"):
                lines.append(f"   {r['body'][:200]}")
            lines.append("")
        return "\n".join(lines)
