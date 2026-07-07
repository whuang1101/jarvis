from __future__ import annotations

from pathlib import Path

from jarvis.status import build_default_status


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
