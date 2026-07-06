from __future__ import annotations

import jarvis.settings as settings_module
from jarvis.commands import handle_command


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
