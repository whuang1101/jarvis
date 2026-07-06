from __future__ import annotations

import json
from pathlib import Path

from jarvis.tools.edit_file import EditFileTool
from jarvis.tools.read_file import ReadFileTool
from jarvis.tools.list_dir import ListDirTool
from jarvis.tools.search_files import SearchFilesTool
from jarvis.tools.find_symbol import FindSymbolTool
from jarvis.tools.glob_files import GlobFilesTool
from jarvis.tools.sensitive import is_sensitive_path, sensitive_read_error


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

    def test_renders_notebook(self, tmp_path):
        notebook = {
            "cells": [
                {"cell_type": "markdown", "source": ["# Title\n", "Some notes."]},
                {
                    "cell_type": "code",
                    "source": ["print('hi')"],
                    "outputs": [
                        {"output_type": "stream", "text": ["hi\n"]},
                        {
                            "output_type": "execute_result",
                            "data": {"text/plain": ["42"]},
                        },
                        {
                            "output_type": "display_data",
                            "data": {"image/png": "base64data"},
                        },
                    ],
                },
            ],
        }
        f = tmp_path / "nb.ipynb"
        f.write_text(json.dumps(notebook))
        result = ReadFileTool().execute({"path": str(f)})
        assert "# %% [markdown]" in result
        assert "# Title" in result
        assert "Some notes." in result
        assert "# %% [code]" in result
        assert "print('hi')" in result
        assert "# Out:" in result
        assert "hi" in result
        assert "42" in result
        assert "cell_type" not in result
        assert "base64data" not in result

    def test_malformed_notebook_returns_error(self, tmp_path):
        f = tmp_path / "bad.ipynb"
        f.write_text("not json")
        result = ReadFileTool().execute({"path": str(f)})
        assert result.startswith("Error")

    def test_extracts_pdf_text(self, tmp_path):
        import pypdf
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=200, height=200)
        page = writer.pages[0]

        content = DecodedStreamObject()
        content.set_data(b"BT /F1 24 Tf 10 100 Td (Hello PDF) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(content)

        font = DictionaryObject()
        font[NameObject("/Type")] = NameObject("/Font")
        font[NameObject("/Subtype")] = NameObject("/Type1")
        font[NameObject("/BaseFont")] = NameObject("/Helvetica")
        resources = DictionaryObject()
        resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        page[NameObject("/Resources")] = resources

        f = tmp_path / "doc.pdf"
        with open(f, "wb") as fh:
            writer.write(fh)

        result = ReadFileTool().execute({"path": str(f)})
        assert "Hello PDF" in result

    def test_non_pdf_with_pdf_extension_returns_error(self, tmp_path):
        f = tmp_path / "fake.pdf"
        f.write_text("this is not a pdf")
        result = ReadFileTool().execute({"path": str(f)})
        assert result.startswith("Error")


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


class TestGlobFiles:
    def test_matches_newest_first(self, tmp_path):
        import os
        import time

        (tmp_path / "sub").mkdir()
        (tmp_path / "a.py").write_text("")
        time.sleep(0.01)
        (tmp_path / "sub" / "b.py").write_text("")
        (tmp_path / "sub" / ".hidden.py").write_text("")
        os.utime(tmp_path / "a.py", (1000, 1000))
        os.utime(tmp_path / "sub" / "b.py", (2000, 2000))

        result = GlobFilesTool().execute({"pattern": "**/*.py", "path": str(tmp_path)})
        lines = result.splitlines()
        assert lines == [str(Path("sub") / "b.py"), "a.py"]

    def test_no_matches(self, tmp_path):
        result = GlobFilesTool().execute({"pattern": "*.nope", "path": str(tmp_path)})
        assert result == "No files match *.nope"

    def test_missing_path(self, tmp_path):
        result = GlobFilesTool().execute({"pattern": "*.py", "path": str(tmp_path / "nope")})
        assert result.startswith("Error")


class TestSensitive:
    def test_sensitive_paths(self):
        for path in (".env", "/tmp/proj/.env.local", "key.pem", "id_rsa", "~/.netrc"):
            assert is_sensitive_path(path) is True

    def test_non_sensitive_paths(self):
        for path in ("main.py", "README.env.md", "envvars.py"):
            assert is_sensitive_path(path) is False

    def test_read_error_message(self):
        assert sensitive_read_error("x").startswith("Error:")
