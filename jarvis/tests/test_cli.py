from __future__ import annotations

import pytest

import jarvis.cli as cli
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
