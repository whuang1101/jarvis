from __future__ import annotations

import jarvis.sessions as sessions_module
import jarvis.settings as settings_module
from jarvis.commands import handle_command
from jarvis.context import ContextManager
from jarvis.sessions import SessionStore


class TestConfigCommand:
    def test_no_args_lists_effective_settings_and_sources(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)

        handle_command("/config", None, None, None)

        out = capsys.readouterr().out
        assert "theme" in out
        assert "(default)" in out

    def test_set_writes_to_global_config(self, tmp_path, monkeypatch, capsys):
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", config_path)
        monkeypatch.chdir(tmp_path)

        handle_command("/config theme dracula", None, None, None)

        settings = settings_module.Settings.load(config_path)
        assert settings.theme == "dracula"
        out = capsys.readouterr().out
        assert "theme" in out

    def test_set_shows_new_value_as_global_source(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", config_path)
        monkeypatch.chdir(tmp_path)

        handle_command("/config max_tool_iterations 7", None, None, None)

        settings, sources = settings_module.Settings.load_with_sources(config_path)
        assert settings.max_tool_iterations == 7
        assert sources["max_tool_iterations"] == "global"

    def test_unknown_key_reports_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)

        handle_command("/config made_up_key 5", None, None, None)

        out = capsys.readouterr().out
        assert "Unknown setting" in out

    def test_missing_value_reports_usage_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)

        handle_command("/config theme", None, None, None)

        out = capsys.readouterr().out
        assert "Usage" in out


class TestSessionsCommand:
    def test_lists_no_sessions(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sessions_module, "_SESSIONS_DIR", tmp_path / "missing")

        handle_command("/sessions", None, None, None)

        out = capsys.readouterr().out
        assert "No saved sessions" in out

    def test_lists_recent_sessions(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sessions_module, "_SESSIONS_DIR", tmp_path)
        SessionStore(cwd="/some/project", session_id="20260101-100000-aaaaaa").save(
            [{"role": "user", "content": "hello there"}]
        )

        handle_command("/sessions", None, None, None)

        out = capsys.readouterr().out
        assert "2026-01-01 10:00" in out
        assert "/some/project" in out
        assert "hello there" in out


class TestResumeCommand:
    def test_resume_loads_history_into_context(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sessions_module, "_SESSIONS_DIR", tmp_path)
        SessionStore(cwd="/some/project", session_id="20260101-100000-aaaaaa").save(
            [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        )
        context = ContextManager()
        session = SessionStore(cwd="/current/dir")

        handle_command("/resume 1", None, context, None, session)

        assert context._history == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        assert session.session_id == "20260101-100000-aaaaaa"
        assert session.cwd == "/some/project"
        out = capsys.readouterr().out
        assert "Resumed session" in out

    def test_resume_out_of_range_reports_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sessions_module, "_SESSIONS_DIR", tmp_path)

        handle_command("/resume 3", None, ContextManager(), None)

        out = capsys.readouterr().out
        assert "No session #3" in out

    def test_resume_without_arg_reports_usage(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sessions_module, "_SESSIONS_DIR", tmp_path)

        handle_command("/resume", None, ContextManager(), None)

        out = capsys.readouterr().out
        assert "Usage" in out
