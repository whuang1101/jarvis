from __future__ import annotations

from typing import Any

from .base import BaseTool

_MAX_CHARS = 12_000


class WebExtractTool(BaseTool):
    name = "web_extract"
    description = (
        "Fetch a URL and extract its main content as clean text — removes ads, nav bars, "
        "and boilerplate. Better than fetch_url for articles and documentation pages."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch and extract."},
        },
        "required": ["url"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        url: str = args["url"]
        try:
            import trafilatura
        except ImportError:
            return "Error: trafilatura not installed. Run: pip install trafilatura"

        try:
            downloaded = trafilatura.fetch_url(url)
        except Exception as e:
            return f"Error fetching {url}: {e}"

        if not downloaded:
            return f"Error: could not download {url}"

        text = trafilatura.extract(
            downloaded,
            favor_precision=True,
            include_comments=False,
            include_tables=True,
        )

        if not text:
            return f"Error: could not extract content from {url} (page may require JavaScript)"

        if len(text) > _MAX_CHARS:
            return text[:_MAX_CHARS] + f"\n\n[... truncated — {len(text):,} total chars]"
        return text
