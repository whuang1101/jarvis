from __future__ import annotations

import time

from jarvis.agent import truncate_tool_result, execute_with_timeout
from jarvis.tools.base import BaseTool
from jarvis.tools.read_file import ReadFileTool


class TestTruncateToolResult:
    def test_short_result_unchanged(self):
        assert truncate_tool_result("hello") == "hello"

    def test_long_result_truncated(self):
        result = truncate_tool_result("x" * 50_000)
        assert len(result) < 10_000
        assert "chars omitted" in result
        assert result.startswith("x" * 100)
        assert result.endswith("x" * 100)


class _SleepTool(BaseTool):
    name = "sleep_tool"
    description = "test"
    parameters = {"type": "object", "properties": {}}

    def execute(self, args):
        time.sleep(args.get("secs", 0))
        return "done"


class TestExecuteWithTimeout:
    def test_fast_tool_returns(self):
        assert execute_with_timeout(_SleepTool(), {"secs": 0}, timeout=5) == "done"

    def test_slow_tool_times_out(self):
        result = execute_with_timeout(_SleepTool(), {"secs": 2}, timeout=1)
        assert result.startswith("Error: tool timed out")


class TestReadFileGuards:
    def test_large_file_requires_slice(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * 200_000)
        result = ReadFileTool().execute({"path": str(f)})
        assert result.startswith("Error") and "offset" in result

    def test_large_file_slice_works(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("\n".join(f"line{i}" for i in range(1, 50_001)))
        result = ReadFileTool().execute({"path": str(f), "offset": 100, "limit": 3})
        assert "100: line100" in result
        assert "103" not in result

    def test_offset_past_end(self, tmp_path):
        f = tmp_path / "s.txt"
        f.write_text("one\ntwo\n")
        result = ReadFileTool().execute({"path": str(f), "offset": 99, "limit": 5})
        assert result.startswith("Error")
