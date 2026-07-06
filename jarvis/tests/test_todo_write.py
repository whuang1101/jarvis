from __future__ import annotations

from jarvis.tools.todo_write import TodoWriteTool


def test_updates_and_renders(capsys) -> None:
    result = TodoWriteTool().execute({
        "todos": [
            {"content": "Write tests", "status": "completed"},
            {"content": "Implement feature", "status": "in_progress"},
            {"content": "Update docs", "status": "pending"},
        ],
    })
    assert result == "Todo list updated (1/3 completed)."
    out = capsys.readouterr().out
    assert "Write tests" in out
    assert "Implement feature" in out
    assert "Update docs" in out


def test_rejects_non_list() -> None:
    result = TodoWriteTool().execute({"todos": "not a list"})
    assert result.startswith("Error")


def test_rejects_bad_status() -> None:
    result = TodoWriteTool().execute({"todos": [{"content": "x", "status": "bogus"}]})
    assert result.startswith("Error")


def test_rejects_empty_content() -> None:
    result = TodoWriteTool().execute({"todos": [{"content": "  ", "status": "pending"}]})
    assert result.startswith("Error")


def test_empty_list_ok(capsys) -> None:
    result = TodoWriteTool().execute({"todos": []})
    assert result == "Todo list updated (0/0 completed)."
    assert "Todos" in capsys.readouterr().out
