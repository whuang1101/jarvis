from __future__ import annotations

from typing import Any

from .base import BaseTool
from .read_file import ReadFileTool
from .write_file import WriteFileTool
from .run_command import RunCommandTool
from .list_dir import ListDirTool
from .search_files import SearchFilesTool
from .fetch_url import FetchUrlTool
from .package_info import PackageInfoTool
from .find_symbol import FindSymbolTool

_REGISTRY: list[BaseTool] = [
    ReadFileTool(),
    WriteFileTool(),
    RunCommandTool(),
    ListDirTool(),
    SearchFilesTool(),
    FetchUrlTool(),
    PackageInfoTool(),
    FindSymbolTool(),
]

_BY_NAME: dict[str, BaseTool] = {t.name: t for t in _REGISTRY}


def get_all_tools() -> list[BaseTool]:
    return list(_REGISTRY)


def get_tool_by_name(name: str) -> BaseTool | None:
    return _BY_NAME.get(name)


def register_tool(tool: BaseTool) -> None:
    _REGISTRY.append(tool)
    _BY_NAME[tool.name] = tool
