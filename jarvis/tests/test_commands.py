from __future__ import annotations

import types
from pathlib import Path

import jarvis.commands as commands_module
import jarvis.mcp_manager as mcp_manager
import jarvis.permissions as permissions_module
import jarvis.sessions as sessions_module
import jarvis.settings as settings_module
import jarvis.todos as todos_module
from jarvis import checkpoints
from jarvis.commands import append_memory, handle_command
from jarvis.context import ContextManager, UsageTracker
from jarvis.sessions import SessionStore


class TestAppendMemory:
    def test_appends_and_creates_parent_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))

        result = append_memory("recall this")

        assert result == "Memory updated."
        memory_path = tmp_path / ".jarvis" / "memory.md"
        assert memory_path.read_text(encoding="utf-8") == "recall this\n"

    def test_second_call_appends_second_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))

        append_memory("recall this")
        append_memory("and this too")

        memory_path = tmp_path / ".jarvis" / "memory.md"
        content = memory_path.read_text(encoding="utf-8")
        assert content == "recall this\nand this too\n"


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


class TestStatuslineCommand:
    def test_no_args_shows_default(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)

        handle_command("/statusline", None, None, None)

        out = capsys.readouterr().out
        assert "status" in out.lower()
        assert "(default)" in out

    def test_sets_and_persists_statusline(self, tmp_path, monkeypatch, capsys):
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", config_path)
        monkeypatch.chdir(tmp_path)

        handle_command("/statusline my-status-cmd", None, None, None)

        settings = settings_module.Settings.load(config_path)
        assert settings.statusline == "my-status-cmd"
        out = capsys.readouterr().out
        assert "status" in out.lower()

    def test_off_clears_statusline(self, tmp_path, monkeypatch, capsys):
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(settings_module, "_CONFIG_PATH", config_path)
        monkeypatch.chdir(tmp_path)

        handle_command("/statusline my-status-cmd", None, None, None)
        handle_command("/statusline off", None, None, None)

        settings = settings_module.Settings.load(config_path)
        assert settings.statusline == ""
        out = capsys.readouterr().out
        assert "status" in out.lower()


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


class TestCustomCommands:
    def test_global_command_renders_arguments_and_runs_agent(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "explain.md").write_text("Explain this code simply: $ARGUMENTS", encoding="utf-8")
        monkeypatch.setattr(commands_module, "_CUSTOM_COMMANDS_GLOBAL_DIR", global_dir)
        monkeypatch.chdir(tmp_path)

        result = handle_command("/explain context.py", None, None, None)

        assert result == f"{commands_module._RUN_AGENT_PREFIX}Explain this code simply: context.py"

    def test_project_command_used_when_no_global_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(commands_module, "_CUSTOM_COMMANDS_GLOBAL_DIR", tmp_path / "missing")
        project_dir = tmp_path / ".jarvis" / "commands"
        project_dir.mkdir(parents=True)
        (project_dir / "triage.md").write_text("Triage: $ARGUMENTS", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = handle_command("/triage foo.py", None, None, None)

        assert result == f"{commands_module._RUN_AGENT_PREFIX}Triage: foo.py"

    def test_global_command_takes_precedence_over_project(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "explain.md").write_text("Global: $ARGUMENTS", encoding="utf-8")
        monkeypatch.setattr(commands_module, "_CUSTOM_COMMANDS_GLOBAL_DIR", global_dir)
        project_dir = tmp_path / ".jarvis" / "commands"
        project_dir.mkdir(parents=True)
        (project_dir / "explain.md").write_text("Project: $ARGUMENTS", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = handle_command("/explain x", None, None, None)

        assert result == f"{commands_module._RUN_AGENT_PREFIX}Global: x"

    def test_unknown_command_with_no_matching_file_reports_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(commands_module, "_CUSTOM_COMMANDS_GLOBAL_DIR", tmp_path / "missing")
        monkeypatch.chdir(tmp_path)

        result = handle_command("/nosuchcommand", None, None, None)

        assert result is None
        out = capsys.readouterr().out
        assert "Unknown command" in out

    def test_help_lists_discovered_custom_commands(self, tmp_path, monkeypatch, capsys):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "explain.md").write_text("Explain: $ARGUMENTS", encoding="utf-8")
        monkeypatch.setattr(commands_module, "_CUSTOM_COMMANDS_GLOBAL_DIR", global_dir)
        monkeypatch.chdir(tmp_path)

        handle_command("/help", None, None, None)

        out = capsys.readouterr().out
        assert "/explain" in out


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    import subprocess as sp

    return sp.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestCommitCommand:
    def test_stages_and_prompts_agent_with_staged_diff(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd == ["git", "add", "-A"]:
                return _completed()
            if cmd == ["git", "diff", "--staged"]:
                return _completed(stdout="diff --git a/foo.py b/foo.py\n+print(1)\n")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/commit", None, None, None)

        assert calls == [["git", "add", "-A"], ["git", "diff", "--staged"]]
        assert result.startswith(commands_module._RUN_AGENT_PREFIX)
        assert "diff --git a/foo.py b/foo.py" in result
        assert "git commit" in result

    def test_add_failure_reports_error(self, monkeypatch, capsys):
        def fake_run(cmd, **kwargs):
            if cmd == ["git", "add", "-A"]:
                return _completed(stderr="fatal: not a git repository", returncode=128)
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/commit", None, None, None)

        assert result is None
        assert "git add failed" in capsys.readouterr().out

    def test_nothing_staged_reports_error(self, monkeypatch, capsys):
        def fake_run(cmd, **kwargs):
            if cmd == ["git", "add", "-A"]:
                return _completed()
            if cmd == ["git", "diff", "--staged"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/commit", None, None, None)

        assert result is None
        assert "Nothing staged" in capsys.readouterr().out


class TestReviewCommand:
    def test_no_arg_diffs_against_main(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _completed(stdout="diff --git a/bar.py b/bar.py\n+print(2)\n")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/review", None, None, None)

        assert calls == [["git", "diff", "main"]]
        assert result.startswith(commands_module._RUN_AGENT_PREFIX)
        assert "diff --git a/bar.py b/bar.py" in result
        assert "the diff against main" in result

    def test_pr_arg_uses_gh_pr_diff(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return _completed(stdout="diff --git a/baz.py b/baz.py\n+print(3)\n")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/review 42", None, None, None)

        assert calls == [["gh", "pr", "diff", "42"]]
        assert result.startswith(commands_module._RUN_AGENT_PREFIX)
        assert "PR #42" in result

    def test_fetch_failure_reports_error(self, monkeypatch, capsys):
        def fake_run(cmd, **kwargs):
            return _completed(stderr="fatal: bad revision 'main'", returncode=128)

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/review", None, None, None)

        assert result is None
        assert "Failed to fetch diff" in capsys.readouterr().out

    def test_no_changes_reports_error(self, monkeypatch, capsys):
        def fake_run(cmd, **kwargs):
            return _completed(stdout="")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        result = handle_command("/review", None, None, None)

        assert result is None
        assert "No changes found" in capsys.readouterr().out


class TestPrContext:
    def test_returns_context_with_branch_commits_and_diff(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return _completed(stdout="feat/x\n")
            if cmd == ["git", "log", "main..HEAD", "--pretty=format:%s"]:
                return _completed(stdout="Add feature x")
            if cmd == ["git", "diff", "main...HEAD"]:
                return _completed(stdout="diff --git a/x.py b/x.py\n+print(1)\n")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        context, error = commands_module._pr_context()

        assert error is None
        assert "feat/x" in context
        assert "Add feature x" in context
        assert "diff --git a/x.py b/x.py" in context

    def test_on_main_reports_error(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return _completed(stdout="main\n")
            if cmd == ["git", "log", "main..HEAD", "--pretty=format:%s"]:
                return _completed(stdout="")
            if cmd == ["git", "diff", "main...HEAD"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        context, error = commands_module._pr_context()

        assert context is None
        assert "main" in error

    def test_empty_diff_reports_error(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return _completed(stdout="feat/x\n")
            if cmd == ["git", "log", "main..HEAD", "--pretty=format:%s"]:
                return _completed(stdout="")
            if cmd == ["git", "diff", "main...HEAD"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        monkeypatch.setattr(commands_module.subprocess, "run", fake_run)

        context, error = commands_module._pr_context()

        assert context is None
        assert "No commits" in error


class TestTodosCommand:
    def test_shows_current_todos(self, capsys):
        todos_module.set_todos([{"content": "step one", "status": "in_progress"}])

        result = handle_command("/todos", None, None, None)

        assert result is None
        assert "step one" in capsys.readouterr().out

    def test_clear_empties_the_list(self):
        todos_module.set_todos([{"content": "step one", "status": "in_progress"}])

        result = handle_command("/todos clear", None, None, None)

        assert result is None
        assert todos_module.get_todos() == []


class TestSandboxCommand:
    def test_on_enables_sandbox(self):
        result = handle_command("/sandbox on", None, None, None)

        assert result is None
        assert permissions_module.is_sandbox() is True

    def test_off_disables_sandbox(self):
        result = handle_command("/sandbox off", None, None, None)

        assert result is None
        assert permissions_module.is_sandbox() is False

    def test_no_arg_reports_status_without_raising(self, capsys):
        result = handle_command("/sandbox", None, None, None)

        assert result is None
        assert "andbox" in capsys.readouterr().out


class TestRewindCommand:
    def test_lists_checkpoints(self, capsys):
        checkpoints.clear()
        checkpoints.create([{"role": "user", "content": "first"}], label="first")

        result = handle_command("/rewind", None, ContextManager(), None)

        assert result is None
        assert "first" in capsys.readouterr().out

    def test_restores_checkpoint_history(self, capsys):
        checkpoints.clear()
        checkpoints.create([{"role": "user", "content": "first"}], label="first")
        context = ContextManager()
        context._history = [{"role": "user", "content": "other"}]

        result = handle_command("/rewind 1", None, context, None)

        assert result is None
        assert context._history == [{"role": "user", "content": "first"}]

    def test_clear_empties_checkpoints(self):
        checkpoints.create([{"role": "user", "content": "first"}], label="first")

        result = handle_command("/rewind clear", None, ContextManager(), None)

        assert result is None
        assert checkpoints.list_checkpoints() == []


class TestUsageCommand:
    def test_reports_cached_tokens_and_hit_rate(self, capsys):
        client = types.SimpleNamespace(current_deployment=lambda: "fake-deployment")
        tracker = UsageTracker()
        tracker.record(100, 20, cached=25)

        result = handle_command("/usage", client, ContextManager(), tracker)

        assert result is None
        out = capsys.readouterr().out
        assert "Cached (of prompt)" in out
        assert "25" in out
        assert "25% hit" in out


class TestMcpCommand:
    def test_list_shows_connected_servers(self, capsys):
        fake = types.SimpleNamespace(
            list_servers=lambda: [{"name": "srv", "tool_count": 3}],
            connect=lambda **kwargs: [],
            disconnect=lambda name: ["x"],
        )
        mcp_manager.set_active_manager(fake)
        try:
            result = handle_command("/mcp", None, None, None)

            assert result is None
            out = capsys.readouterr().out
            assert "srv" in out
            assert "3" in out
        finally:
            mcp_manager.set_active_manager(None)

    def test_remove_reports_removed_tools(self, capsys):
        fake = types.SimpleNamespace(
            list_servers=lambda: [{"name": "srv", "tool_count": 3}],
            connect=lambda **kwargs: [],
            disconnect=lambda name: ["x"],
        )
        mcp_manager.set_active_manager(fake)
        try:
            result = handle_command("/mcp remove srv", None, None, None)

            assert result is None
            assert "Removed srv" in capsys.readouterr().out
        finally:
            mcp_manager.set_active_manager(None)


class TestSkillsCommand:
    def test_lists_discovered_skill_name_and_description(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "home"
        global_dir = home / ".jarvis" / "skills"
        global_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.chdir(tmp_path)
        (global_dir / "hello.md").write_text(
            "---\nname: hello\ndescription: says hello\n---\nHello body.\n"
        )

        result = handle_command("/skills", None, None, None)

        assert result is None
        out = capsys.readouterr().out
        assert "hello" in out
        assert "says hello" in out

    def test_no_skills_reports_message(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.chdir(tmp_path)

        result = handle_command("/skills", None, None, None)

        assert result is None
        assert "No skills found" in capsys.readouterr().out
