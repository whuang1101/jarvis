from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_GLOBAL_SKILLS_DIRNAME = Path(".jarvis") / "skills"
_PROJECT_SKILLS_DIRNAME = Path(".jarvis") / "skills"


def _skill_dirs() -> list[Path]:
    from . import plugins

    return [
        Path.home() / _GLOBAL_SKILLS_DIRNAME,
        Path.cwd() / _PROJECT_SKILLS_DIRNAME,
        *plugins.plugin_skill_dirs(),
    ]


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path


def _parse(path: Path) -> Skill:
    """Parse a skill file: an optional leading `---`-fenced frontmatter block with
    `name:`/`description:` keys, followed by the skill body."""
    text = path.read_text(encoding="utf-8")
    name = path.stem if path.stem != "SKILL" else path.parent.name
    description = ""
    body = text

    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() != "---":
                continue
            for line in lines[1:i]:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "name" and value:
                    name = value
                elif key == "description":
                    description = value
            body = "".join(lines[i + 1:])
            break

    return Skill(name=name, description=description, body=body, path=path)


def _find_skill_files(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    files = []
    for entry in base.iterdir():
        if entry.is_file() and entry.suffix == ".md":
            files.append(entry)
        elif entry.is_dir():
            skill_md = entry / "SKILL.md"
            if skill_md.is_file():
                files.append(skill_md)
    return files


def discover_skills() -> list[Skill]:
    """Discover skills from the global (~/.jarvis/skills) and project (./.jarvis/skills)
    directories. Project skills override global ones with the same name."""
    skills: dict[str, Skill] = {}
    for base in _skill_dirs():
        for path in _find_skill_files(base):
            skill = _parse(path)
            skills[skill.name] = skill
    return sorted(skills.values(), key=lambda s: s.name)


def load_skill(name: str) -> Skill | None:
    """Load a single skill by name, project overriding global."""
    for skill in discover_skills():
        if skill.name == name:
            return skill
    return None
