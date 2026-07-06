from __future__ import annotations

import json

import jarvis.logger as logger_module
from jarvis.logger import SessionLogger


def _read_entries(logger: SessionLogger) -> list[dict]:
    return [json.loads(line) for line in logger.path.read_text().splitlines()]


class TestLogLevels:
    def test_default_level_is_info_and_skips_debug_entries(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        logger = SessionLogger(cwd="/tmp")
        logger.debug("verbose detail")
        logger.user("hello")

        entries = _read_entries(logger)
        types = [e["type"] for e in entries]
        assert "debug" not in types
        assert "user" in types

    def test_debug_level_keeps_debug_entries(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        logger = SessionLogger(cwd="/tmp", level="debug")
        logger.debug("verbose detail")

        entries = _read_entries(logger)
        debug_entries = [e for e in entries if e["type"] == "debug"]
        assert len(debug_entries) == 1
        assert debug_entries[0]["message"] == "verbose detail"
        assert debug_entries[0]["level"] == "debug"

    def test_error_always_written_regardless_of_level(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        logger = SessionLogger(cwd="/tmp", level="info")
        logger.error("boom")

        entries = _read_entries(logger)
        error_entries = [e for e in entries if e["type"] == "error"]
        assert len(error_entries) == 1
        assert error_entries[0]["level"] == "error"

    def test_every_entry_has_a_level_field(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        logger = SessionLogger(cwd="/tmp")
        logger.user("hi")
        logger.assistant("hello")

        entries = _read_entries(logger)
        assert all("level" in e for e in entries)
