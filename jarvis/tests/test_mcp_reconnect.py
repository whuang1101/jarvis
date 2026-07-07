from __future__ import annotations

from jarvis.mcp_manager import MCPManager


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
