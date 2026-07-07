from __future__ import annotations

_TODOS: list[dict[str, str]] = []


def set_todos(todos: list[dict[str, str]]) -> None:
    _TODOS[:] = [dict(t) for t in todos]


def get_todos() -> list[dict[str, str]]:
    return [dict(t) for t in _TODOS]


def clear_todos() -> None:
    _TODOS.clear()


def summary() -> str:
    if not _TODOS:
        return ""
    done = sum(1 for t in _TODOS if t["status"] == "completed")
    return f"{done}/{len(_TODOS)} done"
