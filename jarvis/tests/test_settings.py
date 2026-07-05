from __future__ import annotations

from jarvis.settings import Settings


class TestSettingsLoad:
    def test_missing_file_uses_defaults(self, tmp_path):
        settings = Settings.load(tmp_path / "does_not_exist.toml")
        assert settings == Settings()

    def test_partial_file_overlays_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('max_tool_iterations = 10\ntheme = "solarized"\n')
        settings = Settings.load(path)
        assert settings.max_tool_iterations == 10
        assert settings.theme == "solarized"
        # Untouched keys keep their defaults
        assert settings.auto_mode is False
        assert settings.autocompact_tokens == 25_000
        assert settings.tool_timeout_secs == 60

    def test_full_file_overrides_all_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            "auto_mode = true\n"
            "max_tool_iterations = 5\n"
            "autocompact_tokens = 1000\n"
            "tool_timeout_secs = 30\n"
            'theme = "dracula"\n'
        )
        settings = Settings.load(path)
        assert settings == Settings(
            auto_mode=True,
            max_tool_iterations=5,
            autocompact_tokens=1000,
            tool_timeout_secs=30,
            theme="dracula",
        )

    def test_malformed_file_warns_and_falls_back_to_defaults(self, tmp_path, capsys):
        path = tmp_path / "config.toml"
        path.write_text("this is not [valid toml")
        settings = Settings.load(path)
        assert settings == Settings()
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    def test_unknown_keys_are_ignored(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('made_up_key = "whatever"\ntheme = "monokai"\n')
        settings = Settings.load(path)
        assert settings == Settings(theme="monokai")


class TestProjectConfigOverlay:
    def test_project_config_in_cwd_overlays_global(self, tmp_path):
        global_path = tmp_path / "global.toml"
        global_path.write_text('theme = "dracula"\nmax_tool_iterations = 5\n')
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".jarvis.toml").write_text('theme = "solarized"\n')

        settings = Settings.load(global_path, cwd=project_dir)
        assert settings.theme == "solarized"  # project wins
        assert settings.max_tool_iterations == 5  # untouched global value kept

    def test_project_config_found_in_parent_directory(self, tmp_path):
        (tmp_path / ".jarvis.toml").write_text("auto_mode = true\n")
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)

        settings = Settings.load(tmp_path / "no-global.toml", cwd=nested)
        assert settings.auto_mode is True

    def test_no_project_config_falls_back_to_global_only(self, tmp_path):
        global_path = tmp_path / "global.toml"
        global_path.write_text('theme = "dracula"\n')
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        settings = Settings.load(global_path, cwd=project_dir)
        assert settings.theme == "dracula"

    def test_malformed_project_config_warns_and_is_skipped(self, tmp_path, capsys):
        global_path = tmp_path / "global.toml"
        global_path.write_text('theme = "dracula"\n')
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".jarvis.toml").write_text("not [valid toml")

        settings = Settings.load(global_path, cwd=project_dir)
        assert settings.theme == "dracula"
        captured = capsys.readouterr()
        assert "Warning" in captured.err
