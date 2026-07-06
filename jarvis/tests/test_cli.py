from __future__ import annotations

import pytest

import jarvis.cli as cli
import jarvis.commands as commands_module
import jarvis.logger as logger_module
import jarvis.permissions as permissions_module


class _FakeConfig:
    @classmethod
    def load(cls):
        return cls()


class _FakeClient:
    def __init__(self, config):
        pass

    def current_deployment(self) -> str:
        return "fake-deployment"


class TestParseArgs:
    def test_no_args(self):
        args = cli._parse_args([])
        assert args.prompt is None
        assert args.mcp is False

    def test_dash_p(self):
        args = cli._parse_args(["-p", "what is 2+2"])
        assert args.prompt == "what is 2+2"
        assert args.mcp is False

    def test_dash_p_with_mcp(self):
        args = cli._parse_args(["-p", "hello", "--mcp"])
        assert args.prompt == "hello"
        assert args.mcp is True

    def test_continue_flag_defaults_false(self):
        args = cli._parse_args([])
        assert args.continue_ is False

    def test_continue_flag(self):
        args = cli._parse_args(["--continue"])
        assert args.continue_ is True

    def test_debug_flag_defaults_false(self):
        args = cli._parse_args([])
        assert args.debug is False

    def test_debug_flag(self):
        args = cli._parse_args(["--debug"])
        assert args.debug is True


class TestReadFullInput:
    def test_single_line_passthrough(self, monkeypatch):
        monkeypatch.setattr(cli, "_read_input", lambda status: "hello")
        assert cli._read_full_input("status") == "hello"

    def test_backslash_continuation_joins_lines(self, monkeypatch):
        monkeypatch.setattr(cli, "_read_input", lambda status: "line one\\")
        responses = iter(["line two"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
        assert cli._read_full_input("status") == "line one\nline two"

    def test_backslash_continuation_multiple_lines(self, monkeypatch):
        monkeypatch.setattr(cli, "_read_input", lambda status: "one\\")
        responses = iter(["two\\", "three"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
        assert cli._read_full_input("status") == "one\ntwo\nthree"

    def test_triple_backtick_block_reads_until_closing_fence(self, monkeypatch):
        monkeypatch.setattr(cli, "_read_input", lambda status: "```")
        responses = iter(["def f():", "    pass", "```"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
        assert cli._read_full_input("status") == "def f():\n    pass"

    def test_backslash_continuation_eof_returns_partial(self, monkeypatch):
        monkeypatch.setattr(cli, "_read_input", lambda status: "only line\\")

        def raise_eof(prompt=""):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        assert cli._read_full_input("status") == "only line"


class TestOneShotMode(object):
    @pytest.fixture(autouse=True)
    def _isolate_logs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(cli, "Config", _FakeConfig)
        monkeypatch.setattr(cli, "JarvisClient", _FakeClient)
        monkeypatch.setattr(permissions_module, "_auto_mode", False)

    def test_prints_answer_and_exits_zero(self, monkeypatch):
        calls = {}

        def fake_run_agent(message, client, context, tracker, logger, session):
            calls["message"] = message
            print("4")

        monkeypatch.setattr(cli, "run_agent", fake_run_agent)
        monkeypatch.setattr(cli, "_init_mcp", lambda mcp: pytest.fail("MCP should not connect without --mcp"))

        import sys
        monkeypatch.setattr(sys, "argv", ["jarvis", "-p", "what is 2+2"])
        with pytest.raises(SystemExit) as exc:
            cli.main()

        assert exc.value.code == 0
        assert calls["message"] == "what is 2+2"
        assert cli.is_auto_mode() is True

    def test_connects_mcp_when_flag_passed(self, monkeypatch):
        mcp_connected = {"called": False}

        def fake_init_mcp(mcp):
            mcp_connected["called"] = True

        monkeypatch.setattr(cli, "run_agent", lambda *a, **k: None)
        monkeypatch.setattr(cli, "_init_mcp", fake_init_mcp)

        import sys
        monkeypatch.setattr(sys, "argv", ["jarvis", "-p", "hi", "--mcp"])
        with pytest.raises(SystemExit) as exc:
            cli.main()

        assert exc.value.code == 0
        assert mcp_connected["called"] is True

    def test_debug_flag_sets_debug_level_logger(self, monkeypatch):
        levels = {}
        real_logger_cls = cli.SessionLogger

        class _CapturingLogger(real_logger_cls):
            def __init__(self, cwd, level="info"):
                levels["level"] = level
                super().__init__(cwd, level)

        monkeypatch.setattr(cli, "SessionLogger", _CapturingLogger)
        monkeypatch.setattr(cli, "run_agent", lambda *a, **k: None)
        monkeypatch.setattr(cli, "_init_mcp", lambda mcp: None)

        import sys
        monkeypatch.setattr(sys, "argv", ["jarvis", "-p", "hi", "--debug"])
        with pytest.raises(SystemExit):
            cli.main()

        assert levels["level"] == "debug"

    def test_exit_code_one_on_error(self, monkeypatch, capsys):
        def failing_run_agent(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(cli, "run_agent", failing_run_agent)
        monkeypatch.setattr(cli, "_init_mcp", lambda mcp: None)

        import sys
        monkeypatch.setattr(sys, "argv", ["jarvis", "-p", "hi"])
        with pytest.raises(SystemExit) as exc:
            cli.main()

        assert exc.value.code == 1
        assert "boom" in capsys.readouterr().out


class TestHashMemoryShortcut:
    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(cli, "Config", _FakeConfig)
        monkeypatch.setattr(cli, "JarvisClient", _FakeClient)
        monkeypatch.setattr(permissions_module, "_auto_mode", False)
        monkeypatch.setattr(cli, "_init_mcp", lambda mcp: None)
        monkeypatch.setattr(cli, "run_agent", lambda *a, **k: pytest.fail("agent should not run for a # note"))

        import sys
        monkeypatch.setattr(sys, "argv", ["jarvis"])

    def _run_with_inputs(self, monkeypatch, inputs):
        responses = iter(inputs)

        def fake_read(status):
            try:
                return next(responses)
            except StopIteration:
                raise EOFError

        monkeypatch.setattr(cli, "_read_full_input", fake_read)

    def test_note_is_appended_to_memory_and_not_sent_to_agent(self, monkeypatch, capsys):
        calls = {}

        def fake_append_memory(text):
            calls["text"] = text
            return "Memory updated."

        monkeypatch.setattr(commands_module, "append_memory", fake_append_memory)
        self._run_with_inputs(monkeypatch, ["# remember this thing"])

        cli.main()

        assert calls["text"] == "remember this thing"
        assert "Memory updated." in capsys.readouterr().out

    def test_bare_hash_is_swallowed_without_error(self, monkeypatch, capsys):
        monkeypatch.setattr(
            commands_module,
            "append_memory",
            lambda text: pytest.fail("append_memory should not be called"),
        )
        self._run_with_inputs(monkeypatch, ["#"])

        cli.main()

        assert "Error" not in capsys.readouterr().out


class TestAtPathMention:
    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(logger_module, "_LOG_DIR", tmp_path)
        monkeypatch.setattr(cli, "Config", _FakeConfig)
        monkeypatch.setattr(cli, "JarvisClient", _FakeClient)
        monkeypatch.setattr(permissions_module, "_auto_mode", False)
        monkeypatch.setattr(cli, "_init_mcp", lambda mcp: None)

        import sys
        monkeypatch.setattr(sys, "argv", ["jarvis"])

    def _run_with_inputs(self, monkeypatch, inputs):
        responses = iter(inputs)

        def fake_read(status):
            try:
                return next(responses)
            except StopIteration:
                raise EOFError

        monkeypatch.setattr(cli, "_read_full_input", fake_read)

    def test_at_path_mention_is_expanded_before_dispatch(self, monkeypatch, tmp_path):
        notes = tmp_path / "notes.txt"
        notes.write_text("hello world")
        calls = {}

        def fake_run_agent(message, client, context, tracker, logger, session):
            calls["message"] = message

        monkeypatch.setattr(cli, "run_agent", fake_run_agent)
        self._run_with_inputs(monkeypatch, [f"summarize @{notes} please"])

        cli.main()

        assert "[File:" in calls["message"]
        assert "hello world" in calls["message"]
