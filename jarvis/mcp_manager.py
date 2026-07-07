from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Callable

from .tools.base import BaseTool


class MCPTool(BaseTool):
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        executor: Callable[[dict[str, Any]], str],
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self._executor = executor

    def execute(self, args: dict[str, Any]) -> str:
        return self._executor(args)


class MCPManager:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._servers: dict[str, dict[str, Any]] = {}
        self._server_params: dict[str, dict[str, Any]] = {}

    def list_servers(self) -> list[dict[str, Any]]:
        return sorted(
            (
                {"name": name, "tool_count": len(info.get("tools", []))}
                for name, info in self._servers.items()
            ),
            key=lambda entry: entry["name"],
        )

    def disconnect(self, name: str) -> list[str]:
        if name not in self._servers:
            return []
        info = self._servers.pop(name)
        tool_names = [t.name for t in info.get("tools", [])]
        task = info.get("task")
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass
        return tool_names

    def _run(self, coro: Any, timeout: int = 30) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def connect(self, name: str, command: str, args: list[str], env: dict[str, str]) -> list[MCPTool]:
        self._server_params[name] = {"command": command, "args": list(args), "env": dict(env)}
        ready = threading.Event()
        errors: list[Exception] = []

        async def _connect() -> None:
            try:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client

                params = StdioServerParameters(
                    command=command,
                    args=args,
                    env={**os.environ, **env},
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        self._servers[name] = {
                            "session": session,
                            "tools": tools_result.tools,
                        }
                        ready.set()
                        self._servers[name]["task"] = asyncio.current_task()
                        await asyncio.Event().wait()  # keep session alive
            except Exception as exc:
                errors.append(exc)
                ready.set()

        asyncio.run_coroutine_threadsafe(_connect(), self._loop)
        if not ready.wait(timeout=30) and not errors:
            # Coroutine never signalled readiness and recorded no error: the server
            # hung during initialize()/list_tools(). Fail clearly instead of letting
            # _make_tools raise a bare KeyError on the unregistered server.
            raise TimeoutError(f"{name} did not become ready within 30s")

        if errors:
            raise errors[0]

        return self._make_tools(name)

    def _make_tools(self, server_name: str) -> list[MCPTool]:
        tools = []
        for mcp_tool in self._servers[server_name]["tools"]:
            parameters = dict(mcp_tool.inputSchema) if mcp_tool.inputSchema else {
                "type": "object",
                "properties": {},
            }

            def executor(
                args: dict[str, Any],
                sn: str = server_name,
                tn: str = mcp_tool.name,
            ) -> str:
                return self._call_tool(sn, tn, args)

            tools.append(MCPTool(
                name=mcp_tool.name,
                description=mcp_tool.description or "",
                parameters=parameters,
                executor=executor,
            ))
        return tools

    def _call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        async def _call() -> str:
            session = self._servers[server_name]["session"]
            result = await session.call_tool(tool_name, arguments)
            if not result.content:
                return "(no output)"
            parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    parts.append(item.text)
                else:
                    parts.append(str(item))
            return "\n".join(parts)

        return self._run(_call(), timeout=60)

    def reconnect(self, name: str) -> bool:
        if name not in self._server_params:
            return False
        self.disconnect(name)
        try:
            self.connect(name, **self._server_params[name])
        except Exception:
            return False
        return True


_ACTIVE_MANAGER: MCPManager | None = None


def set_active_manager(manager: MCPManager | None) -> None:
    global _ACTIVE_MANAGER
    _ACTIVE_MANAGER = manager


def get_active_manager() -> MCPManager | None:
    return _ACTIVE_MANAGER
