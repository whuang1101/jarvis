from __future__ import annotations

import json

from jarvis import mcp_config
from jarvis.mcp_config import load_mcp_servers


def test_loads_well_formed_project_config(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_config, "_GLOBAL_CONFIG", tmp_path / "missing" / "mcp.json")
    (tmp_path / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            "one": {"command": "cmd-one", "args": ["--flag"], "env": {"A": "1"}},
            "two": {"command": "cmd-two"},
        }
    }))

    servers = load_mcp_servers(cwd=str(tmp_path))

    by_name = {s["name"]: s for s in servers}
    assert by_name["one"] == {"name": "one", "command": "cmd-one", "args": ["--flag"], "env": {"A": "1"}}
    assert by_name["two"] == {"name": "two", "command": "cmd-two", "args": [], "env": {}}


def test_entry_missing_command_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_config, "_GLOBAL_CONFIG", tmp_path / "missing" / "mcp.json")
    (tmp_path / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"broken": {"args": ["--flag"]}}
    }))

    assert load_mcp_servers(cwd=str(tmp_path)) == []


def test_project_entry_overrides_global(tmp_path, monkeypatch):
    global_config = tmp_path / "global" / "mcp.json"
    global_config.parent.mkdir()
    global_config.write_text(json.dumps({
        "mcpServers": {"shared": {"command": "global-cmd"}}
    }))
    monkeypatch.setattr(mcp_config, "_GLOBAL_CONFIG", global_config)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"shared": {"command": "project-cmd"}}
    }))

    servers = load_mcp_servers(cwd=str(project_dir))

    assert servers == [{"name": "shared", "command": "project-cmd", "args": [], "env": {}}]


def test_malformed_json_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_config, "_GLOBAL_CONFIG", tmp_path / "missing" / "mcp.json")
    (tmp_path / ".mcp.json").write_text("{not valid json")

    assert load_mcp_servers(cwd=str(tmp_path)) == []
