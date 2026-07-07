from __future__ import annotations

from jarvis import todos


def teardown_function(_fn) -> None:
    todos.clear_todos()


def test_set_and_get_round_trip() -> None:
    items = [
        {"content": "Write tests", "status": "completed"},
        {"content": "Implement feature", "status": "in_progress"},
    ]
    todos.set_todos(items)
    result = todos.get_todos()
    assert result == items
    assert result is not todos._TODOS


def test_get_todos_returns_fresh_copies() -> None:
    todos.set_todos([{"content": "a", "status": "pending"}])
    first = todos.get_todos()
    first.append({"content": "b", "status": "pending"})
    first[0]["status"] = "completed"
    second = todos.get_todos()
    assert second == [{"content": "a", "status": "pending"}]


def test_clear_todos() -> None:
    todos.set_todos([{"content": "a", "status": "pending"}])
    todos.clear_todos()
    assert todos.get_todos() == []


def test_summary_empty() -> None:
    todos.clear_todos()
    assert todos.summary() == ""


def test_summary_partial() -> None:
    todos.set_todos([
        {"content": "a", "status": "completed"},
        {"content": "b", "status": "pending"},
    ])
    assert todos.summary() == "1/2 done"
