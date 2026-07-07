from __future__ import annotations

from jarvis.mcp_manager import MCPManager
from jarvis.settings import Settings


def test_reconnect_respawns_with_stored_params():
    mgr = MCPManager()
    calls = []

    def stub_connect(name, **kwargs):
        calls.append((name, kwargs))
        return []

    mgr.connect = stub_connect
    mgr._server_params["srv"] = {"command": "c", "args": [], "env": {}}

    assert mgr.reconnect("srv") is True
    assert len(calls) == 1
    call_name, call_kwargs = calls[0]
    assert call_name == "srv"
    assert call_kwargs == {"command": "c", "args": [], "env": {}}


def test_reconnect_missing_server_returns_false():
    mgr = MCPManager()
    assert mgr.reconnect("missing") is False


def test_reconnect_returns_false_on_connect_failure():
    mgr = MCPManager()

    def stub_connect(name, **kwargs):
        raise RuntimeError("boom")

    mgr.connect = stub_connect
    mgr._server_params["srv"] = {"command": "c", "args": [], "env": {}}

    assert mgr.reconnect("srv") is False


def test_call_tool_retries_once_via_reconnect(monkeypatch):
    mgr = MCPManager()
    calls = []

    results = iter([RuntimeError("boom"), "ok"])

    def stub_run(coro, timeout=30):
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    def stub_reconnect(name):
        calls.append(name)
        return True

    monkeypatch.setattr(mgr, "_run", stub_run)
    monkeypatch.setattr(mgr, "reconnect", stub_reconnect)

    assert mgr._call_tool("srv", "t", {}) == "ok"
    assert calls == ["srv"]


def test_call_tool_returns_error_when_reconnect_fails(monkeypatch):
    mgr = MCPManager()

    def stub_run(coro, timeout=30):
        raise RuntimeError("boom")

    monkeypatch.setattr(mgr, "_run", stub_run)
    monkeypatch.setattr(mgr, "reconnect", lambda name: False)

    result = mgr._call_tool("srv", "t", {})
    assert result.startswith("Error:")


def test_call_tool_skips_reconnect_when_disabled(tmp_path, monkeypatch):
    mgr = MCPManager()
    calls = []

    def stub_run(coro, timeout=30):
        raise RuntimeError("boom")

    def stub_reconnect(name):
        calls.append(name)
        return True

    config = tmp_path / "config.toml"
    config.write_text("mcp_auto_reconnect = false\n")

    original_load = Settings.load

    monkeypatch.setattr(mgr, "_run", stub_run)
    monkeypatch.setattr(mgr, "reconnect", stub_reconnect)
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: original_load(path=config)))

    result = mgr._call_tool("srv", "t", {})
    assert result.startswith("Error:")
    assert calls == []
