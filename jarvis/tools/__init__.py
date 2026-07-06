from __future__ import annotations

from .base import BaseTool
from .read_file import ReadFileTool
from .write_file import WriteFileTool
from .run_command import RunCommandTool
from .task_output import TaskOutputTool
from .list_dir import ListDirTool
from .search_files import SearchFilesTool
from .fetch_url import FetchUrlTool
from .package_info import PackageInfoTool
from .find_symbol import FindSymbolTool
from .web_search import WebSearchTool
from .web_extract import WebExtractTool
from .edit_file import EditFileTool
from .git_tools import GitStatusTool, GitDiffTool, GitLogTool
from .todo_write import TodoWriteTool

_REGISTRY: list[BaseTool] = [
    ReadFileTool(),
    WriteFileTool(),
    EditFileTool(),
    RunCommandTool(),
    TaskOutputTool(),
    ListDirTool(),
    SearchFilesTool(),
    FetchUrlTool(),
    PackageInfoTool(),
    FindSymbolTool(),
    WebSearchTool(),
    WebExtractTool(),
    GitStatusTool(),
    GitDiffTool(),
    GitLogTool(),
    TodoWriteTool(),
]

_BY_NAME: dict[str, BaseTool] = {t.name: t for t in _REGISTRY}


def get_all_tools() -> list[BaseTool]:
    return list(_REGISTRY)


def get_tool_by_name(name: str) -> BaseTool | None:
    return _BY_NAME.get(name)


def register_tool(tool: BaseTool) -> None:
    _REGISTRY.append(tool)
    _BY_NAME[tool.name] = tool
