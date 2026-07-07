from __future__ import annotations

import types

from jarvis.mcp_manager import MCPManager, get_active_manager, set_active_manager


def test_list_servers_and_disconnect():
    mgr = MCPManager()
    mgr._servers["srv"] = {
        "tools": [types.SimpleNamespace(name="a"), types.SimpleNamespace(name="b")],
    }

    assert mgr.list_servers() == [{"name": "srv", "tool_count": 2}]
    assert mgr.disconnect("srv") == ["a", "b"]
    assert "srv" not in mgr._servers
    assert mgr.disconnect("missing") == []


def test_active_manager_handle():
    mgr = MCPManager()
    set_active_manager(mgr)
    try:
        assert get_active_manager() is mgr
    finally:
        set_active_manager(None)
