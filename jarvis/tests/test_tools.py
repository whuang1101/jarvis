from __future__ import annotations

from jarvis.tools.edit_file import EditFileTool
from jarvis.tools.read_file import ReadFileTool
from jarvis.tools.list_dir import ListDirTool
from jarvis.tools.search_files import SearchFilesTool
from jarvis.tools.find_symbol import FindSymbolTool


class TestEditFile:
    def test_missing_file(self, tmp_path):
        result = EditFileTool().execute({"path": str(tmp_path / "nope.txt"), "old_string": "a", "new_string": "b"})
        assert result.startswith("Error")

    def test_old_string_not_found(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("hello world")
        result = EditFileTool().execute({"path": str(f), "old_string": "goodbye", "new_string": "x"})
        assert "not found" in result

    def test_unique_replacement(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("hello world")
        result = EditFileTool().execute({"path": str(f), "old_string": "world", "new_string": "jarvis"})
        assert result == f"Edited {f}"
        assert f.read_text() == "hello jarvis"

    def test_multiple_occurrences_rejected(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("aaa bbb aaa")
        result = EditFileTool().execute({"path": str(f), "old_string": "aaa", "new_string": "c"})
        assert "2 times" in result
        assert f.read_text() == "aaa bbb aaa"  # unchanged

    def test_multiple_occurrences_error_includes_line_numbers(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("aaa\nbbb\naaa\n")
        result = EditFileTool().execute({"path": str(f), "old_string": "aaa", "new_string": "c"})
        assert "lines 1, 3" in result

    def test_replace_all(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("aaa bbb aaa")
        result = EditFileTool().execute(
            {"path": str(f), "old_string": "aaa", "new_string": "c", "replace_all": True}
        )
        assert result == f"Edited {f} (2 replacements)"
        assert f.read_text() == "c bbb c"

    def test_replace_all_single_occurrence(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("hello world")
        result = EditFileTool().execute(
            {"path": str(f), "old_string": "world", "new_string": "jarvis", "replace_all": True}
        )
        assert result == f"Edited {f}"
        assert f.read_text() == "hello jarvis"


class TestReadFile:
    def test_reads_content(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("line1\nline2\n")
        assert "line1" in ReadFileTool().execute({"path": str(f)})

    def test_missing_file(self, tmp_path):
        result = ReadFileTool().execute({"path": str(tmp_path / "nope")})
        assert result.startswith("Error")

    def test_truncates_long_content(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * 20_000)
        result = ReadFileTool().execute({"path": str(f)})
        assert "truncated" in result
        assert len(result) < 20_000


class TestListDir:
    def test_lists_tree(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.txt").write_text("")
        (tmp_path / "top.txt").write_text("")
        result = ListDirTool().execute({"path": str(tmp_path)})
        assert "sub/" in result
        assert "top.txt" in result
        assert "a.txt" in result

    def test_missing_path(self, tmp_path):
        assert ListDirTool().execute({"path": str(tmp_path / "nope")}).startswith("Error")

    def test_gitignore_honored(self, tmp_path):
        (tmp_path / ".gitignore").write_text("ignored/\n")
        (tmp_path / "ignored").mkdir()
        (tmp_path / "kept.txt").write_text("")
        result = ListDirTool().execute({"path": str(tmp_path)})
        assert "ignored" not in result
        assert "kept.txt" in result


class TestSearchFiles:
    def test_finds_pattern(self, tmp_path):
        (tmp_path / "f.py").write_text("def needle():\n    pass\n")
        result = SearchFilesTool().execute({"pattern": "needle", "directory": str(tmp_path)})
        assert "needle" in result and "f.py" in result

    def test_no_matches(self, tmp_path):
        (tmp_path / "f.py").write_text("nothing here\n")
        result = SearchFilesTool().execute({"pattern": "zzz_absent", "directory": str(tmp_path)})
        assert "No matches" in result


class TestFindSymbol:
    def test_finds_definition(self, tmp_path):
        (tmp_path / "f.py").write_text("def target_fn():\n    pass\n\ntarget_fn()\n")
        result = FindSymbolTool().execute({"symbol": "target_fn", "directory": str(tmp_path)})
        assert "[definitions]" in result
        assert "[references]" in result

    def test_word_boundary(self, tmp_path):
        (tmp_path / "f.py").write_text("def foobar():\n    pass\n")
        result = FindSymbolTool().execute({"symbol": "foo", "kind": "definition", "directory": str(tmp_path)})
        assert "No matches" in result
