from __future__ import annotations

import subprocess
from pathlib import Path

from jarvis.settings import Settings
from jarvis.status import build_default_status, render_status


def test_build_default_status_no_flags():
    cwd = Path.home() / "proj"
    assert build_default_status(cwd, 1234, False, False, False) == "~/proj · 1.2k tokens"


def test_build_default_status_all_flags():
    cwd = Path.home() / "proj"
    assert (
        build_default_status(cwd, 1234, True, True, True)
        == "~/proj · 1.2k tokens · PLAN · AUTO · DANGER"
    )


def test_build_default_status_outside_home():
    cwd = Path("/tmp/outside")
    assert build_default_status(cwd, 500, False, False, False) == "/tmp/outside · 0.5k tokens"


def test_render_status_empty_statusline_uses_default():
    settings = Settings(statusline="")
    cwd = Path.home() / "proj"
    assert render_status(settings, cwd, 1234, False, False, False) == "~/proj · 1.2k tokens"


def test_render_status_runs_custom_command(monkeypatch):
    settings = Settings(statusline="my-status-cmd")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=0, stdout="CUSTOM\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cwd = Path.home() / "proj"
    assert render_status(settings, cwd, 1234, False, False, False) == "CUSTOM"


def test_render_status_falls_back_on_timeout(monkeypatch):
    settings = Settings(statusline="my-status-cmd")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="my-status-cmd", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    cwd = Path.home() / "proj"
    assert render_status(settings, cwd, 1234, False, False, False) == "~/proj · 1.2k tokens"


def test_render_status_falls_back_on_nonzero_exit(monkeypatch):
    settings = Settings(statusline="my-status-cmd")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cwd = Path.home() / "proj"
    assert render_status(settings, cwd, 1234, False, False, False) == "~/proj · 1.2k tokens"
