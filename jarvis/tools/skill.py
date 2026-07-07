from __future__ import annotations

from typing import Any

from .base import BaseTool
from ..skills import load_skill


class SkillTool(BaseTool):
    name = "skill"
    description = "Load a named skill's full instructions by name, for on-demand use."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the skill to load."},
        },
        "required": ["name"],
    }

    def execute(self, args: dict[str, Any]) -> str:
        name: str = args["name"]
        skill = load_skill(name)
        if skill is None:
            return f"Error: no skill named '{name}'"
        return skill.body
