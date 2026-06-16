from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import BaseTool


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


class PackageInfoTool(BaseTool):
    name = "package_info"
    description = "Look up a package on npm or PyPI. Returns version, description, and install command."
    parameters = {
        "type": "object",
        "properties": {
            "package": {"type": "string", "description": "Package name to look up."},
            "registry": {
                "type": "string",
                "enum": ["npm", "pypi", "auto"],
                "description": "Which registry to check. 'auto' tries both.",
                "default": "auto",
            },
        },
        "required": ["package"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        package: str = args["package"]
        registry: str = args.get("registry", "auto")
        results: list[str] = []

        if registry in ("npm", "auto"):
            try:
                data = _fetch_json(f"https://registry.npmjs.org/{package}/latest")
                name = data.get("name", package)
                version = data.get("version", "?")
                desc = data.get("description", "")
                homepage = data.get("homepage", "")
                lines = [f"npm  {name}@{version}", f"  {desc}"]
                if homepage:
                    lines.append(f"  {homepage}")
                lines.append(f"  npm install {name}")
                results.append("\n".join(lines))
            except urllib.error.HTTPError:
                if registry == "npm":
                    results.append(f"npm: package '{package}' not found")
            except Exception as e:
                if registry == "npm":
                    results.append(f"npm: {e}")

        if registry in ("pypi", "auto"):
            try:
                data = _fetch_json(f"https://pypi.org/pypi/{package}/json")
                info = data.get("info", {})
                name = info.get("name", package)
                version = info.get("version", "?")
                desc = info.get("summary", "")
                homepage = info.get("home_page", "") or info.get("project_url", "")
                lines = [f"PyPI {name} {version}", f"  {desc}"]
                if homepage:
                    lines.append(f"  {homepage}")
                lines.append(f"  pip install {name}")
                results.append("\n".join(lines))
            except urllib.error.HTTPError:
                if registry == "pypi":
                    results.append(f"PyPI: package '{package}' not found")
            except Exception as e:
                if registry == "pypi":
                    results.append(f"PyPI: {e}")

        return "\n\n".join(results) if results else f"'{package}' not found on npm or PyPI"
