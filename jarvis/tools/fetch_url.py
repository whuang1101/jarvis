from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Any

from .base import BaseTool

_MAX_CHARS = 8_000


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html).strip()
    return html


class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "Fetch the text content of a URL. Useful for reading documentation, GitHub issues, error pages, or any web page."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch."},
        },
        "required": ["url"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        url: str = args["url"]
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 Jarvis/0.1"},
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                content_type = response.headers.get("Content-Type", "")
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code} fetching {url}: {e.reason}"
        except urllib.error.URLError as e:
            return f"Error fetching {url}: {e.reason}"
        except Exception as e:
            return f"Error: {e}"

        text = _strip_html(raw) if "html" in content_type.lower() else raw
        if len(text) > _MAX_CHARS:
            return text[:_MAX_CHARS] + f"\n\n[... truncated — {len(text):,} total chars]"
        return text
