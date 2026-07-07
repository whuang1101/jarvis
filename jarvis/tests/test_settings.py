from __future__ import annotations

from jarvis.settings import Settings, persist_allow_pattern, persist_setting


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
        assert settings.dangerously_skip_permissions is False
        assert settings.autocompact_tokens == 25_000
        assert settings.tool_timeout_secs == 60
        assert settings.show_thinking is True
        assert settings.sandbox is False
        assert settings.sandbox_allow_network is False
        assert settings.vi_mode is False

    def test_statusline_default_is_empty(self, tmp_path):
        settings = Settings.load(tmp_path / "does_not_exist.toml")
        assert settings.statusline == ""

    def test_statusline_from_config(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('statusline = "echo hi"\n')
        settings = Settings.load(path)
        assert settings.statusline == "echo hi"

    def test_full_file_overrides_all_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            "auto_mode = true\n"
            "dangerously_skip_permissions = true\n"
            "max_tool_iterations = 5\n"
            "autocompact_tokens = 1000\n"
            "tool_timeout_secs = 30\n"
            'theme = "dracula"\n'
        )
        settings = Settings.load(path)
        assert settings == Settings(
            auto_mode=True,
            dangerously_skip_permissions=True,
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


class TestShowThinking:
    def test_defaults_true(self):
        assert Settings().show_thinking is True

    def test_project_overlay_can_disable(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".jarvis.toml").write_text("show_thinking = false\n")

        settings = Settings.load(tmp_path / "no-global.toml", cwd=project_dir)
        assert settings.show_thinking is False


class TestVision:
    def test_defaults_true(self):
        assert Settings().vision is True

    def test_global_config_can_disable(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("vision = false\n")

        settings = Settings.load(path=path)
        assert settings.vision is False


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

    def test_project_config_loads_sandbox_flag(self, tmp_path):
        (tmp_path / ".jarvis.toml").write_text("sandbox = true\n")
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)

        settings = Settings.load(tmp_path / "no-global.toml", cwd=nested)
        assert settings.sandbox is True

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


class TestPermissionRules:
    def test_defaults_are_empty(self):
        assert Settings().permission_allow == ()
        assert Settings().permission_deny == ()

    def test_permissions_table_is_parsed(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            "[permissions]\n"
            'allow = ["write_file(*)"]\n'
            'deny = ["run_command(git push*)"]\n'
        )
        settings = Settings.load(path)
        assert settings.permission_allow == ("write_file(*)",)
        assert settings.permission_deny == ("run_command(git push*)",)

    def test_project_permissions_overlay_global(self, tmp_path):
        global_path = tmp_path / "global.toml"
        global_path.write_text('[permissions]\nallow = ["write_file(*)"]\n')
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".jarvis.toml").write_text('[permissions]\ndeny = ["run_command(rm *)"]\n')

        settings = Settings.load(global_path, cwd=project_dir)
        # Project's deny list is layered on top; the global allow list it didn't
        # touch is kept, same overlay semantics as any other setting.
        assert settings.permission_allow == ("write_file(*)",)
        assert settings.permission_deny == ("run_command(rm *)",)

    def test_missing_permissions_table_keeps_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('theme = "dracula"\n')
        settings = Settings.load(path)
        assert settings.permission_allow == ()
        assert settings.permission_deny == ()


class TestHooksConfig:
    def test_defaults_are_empty(self):
        assert Settings().hooks_pre_tool == ()
        assert Settings().hooks_post_tool == ()

    def test_hooks_table_is_parsed(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            "[hooks]\n"
            'pre_tool = [{match = "write_file", run = "./block.sh"}]\n'
            'post_tool = [{match = "*", run = "./notify.sh"}]\n'
        )
        settings = Settings.load(path)
        assert settings.hooks_pre_tool == ({"match": "write_file", "run": "./block.sh"},)
        assert settings.hooks_post_tool == ({"match": "*", "run": "./notify.sh"},)

    def test_project_hooks_overlay_global(self, tmp_path):
        global_path = tmp_path / "global.toml"
        global_path.write_text('[hooks]\npre_tool = [{match = "write_file", run = "./a.sh"}]\n')
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".jarvis.toml").write_text('[hooks]\npost_tool = [{match = "run_command", run = "./b.sh"}]\n')

        settings = Settings.load(global_path, cwd=project_dir)
        assert settings.hooks_pre_tool == ({"match": "write_file", "run": "./a.sh"},)
        assert settings.hooks_post_tool == ({"match": "run_command", "run": "./b.sh"},)

    def test_missing_hooks_table_keeps_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('theme = "dracula"\n')
        settings = Settings.load(path)
        assert settings.hooks_pre_tool == ()
        assert settings.hooks_post_tool == ()


class TestPersistAllowPattern:
    def test_creates_file_with_pattern(self, tmp_path):
        path = tmp_path / "config.toml"
        persist_allow_pattern("run_command(git *)", path)

        settings = Settings.load(path)
        assert settings.permission_allow == ("run_command(git *)",)

    def test_appends_to_existing_allow_list_without_dropping_other_keys(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            'theme = "dracula"\n'
            "\n"
            "[permissions]\n"
            'allow = ["write_file(*)"]\n'
            'deny = ["run_command(rm *)"]\n'
        )

        persist_allow_pattern("run_command(git *)", path)

        settings = Settings.load(path)
        assert settings.theme == "dracula"
        assert settings.permission_allow == ("write_file(*)", "run_command(git *)")
        assert settings.permission_deny == ("run_command(rm *)",)

    def test_duplicate_pattern_is_not_added_twice(self, tmp_path):
        path = tmp_path / "config.toml"
        persist_allow_pattern("run_command(git *)", path)
        persist_allow_pattern("run_command(git *)", path)

        settings = Settings.load(path)
        assert settings.permission_allow == ("run_command(git *)",)

    def test_creates_parent_directory(self, tmp_path):
        path = tmp_path / "nested" / "config.toml"
        persist_allow_pattern("write_file(*)", path)
        assert path.exists()

    def test_preserves_existing_hooks_table(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('[hooks]\npre_tool = [{match = "write_file", run = "./block.sh"}]\n')

        persist_allow_pattern("run_command(git *)", path)

        settings = Settings.load(path)
        assert settings.permission_allow == ("run_command(git *)",)
        assert settings.hooks_pre_tool == ({"match": "write_file", "run": "./block.sh"},)


class TestLoadWithSources:
    def test_all_defaults_when_no_files(self, tmp_path):
        settings, sources = Settings.load_with_sources(tmp_path / "missing.toml", cwd=tmp_path)
        assert settings == Settings()
        assert all(s == "default" for s in sources.values())

    def test_global_only_key_marked_global(self, tmp_path):
        global_path = tmp_path / "config.toml"
        global_path.write_text('theme = "dracula"\n')
        settings, sources = Settings.load_with_sources(global_path, cwd=tmp_path)
        assert settings.theme == "dracula"
        assert sources["theme"] == "global"
        assert sources["max_tool_iterations"] == "default"

    def test_project_override_marked_project(self, tmp_path):
        global_path = tmp_path / "config.toml"
        global_path.write_text('theme = "dracula"\n')
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".jarvis.toml").write_text('theme = "solarized"\n')

        settings, sources = Settings.load_with_sources(global_path, cwd=project_dir)
        assert settings.theme == "solarized"
        assert sources["theme"] == "project"


class TestPersistSetting:
    def test_writes_scalar_string(self, tmp_path):
        path = tmp_path / "config.toml"
        persist_setting("theme", "dracula", path)
        assert Settings.load(path).theme == "dracula"

    def test_writes_int(self, tmp_path):
        path = tmp_path / "config.toml"
        persist_setting("max_tool_iterations", "7", path)
        assert Settings.load(path).max_tool_iterations == 7

    def test_writes_bool(self, tmp_path):
        path = tmp_path / "config.toml"
        persist_setting("auto_mode", "true", path)
        assert Settings.load(path).auto_mode is True

    def test_writes_vi_mode(self, tmp_path):
        path = tmp_path / "config.toml"
        persist_setting("vi_mode", "true", path)
        assert Settings.load(path).vi_mode is True

    def test_preserves_other_keys(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('theme = "dracula"\n\n[permissions]\nallow = ["write_file(*)"]\n')
        persist_setting("max_tool_iterations", "3", path)
        settings = Settings.load(path)
        assert settings.theme == "dracula"
        assert settings.max_tool_iterations == 3
        assert settings.permission_allow == ("write_file(*)",)

    def test_unknown_key_raises(self, tmp_path):
        path = tmp_path / "config.toml"
        try:
            persist_setting("made_up_key", "5", path)
            assert False, "expected ValueError"
        except ValueError as e:
            assert "Unknown setting" in str(e)

    def test_permission_keys_rejected(self, tmp_path):
        path = tmp_path / "config.toml"
        try:
            persist_setting("permission_allow", "write_file(*)", path)
            assert False, "expected ValueError"
        except ValueError:
            pass
