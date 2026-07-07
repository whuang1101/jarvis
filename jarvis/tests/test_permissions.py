from __future__ import annotations

import pytest

import jarvis.permissions as permissions
from jarvis.permissions import (
    _DiffError,
    _edit_diff,
    _suggest_pattern,
    is_sandbox,
    needs_permission,
    request_permission,
    set_dangerously_skip_permissions,
    set_sandbox,
)
from jarvis.settings import Settings

DESTRUCTIVE = [
    "rm -rf /tmp/x",
    "rmdir foo",
    "sudo apt install x",
    "kill 1234",
    "pkill python",
    "killall node",
    "git reset --hard HEAD~1",
    "git clean -fdx",
    "psql -c 'DROP TABLE users'",
    "psql -c 'TRUNCATE users'",
    "mkfs.ext4 /dev/sda1",
    "fdisk /dev/sda",
]

BENIGN = [
    "ls -la",
    "git status",
    "echo hello",
    "python3 -m pytest",
    "grep -rn pattern .",
    "cat file.txt",
]


@pytest.mark.parametrize("cmd", DESTRUCTIVE)
def test_destructive_commands_need_permission(cmd):
    assert needs_permission("run_command", {"command": cmd})


@pytest.mark.parametrize("cmd", BENIGN)
def test_benign_commands_skip_permission(cmd):
    assert not needs_permission("run_command", {"command": cmd})


def test_file_ops_always_need_permission():
    assert needs_permission("write_file", {"path": "x", "content": ""})
    assert needs_permission("edit_file", {"path": "x", "old_string": "a", "new_string": "b"})


def test_read_only_tools_skip_permission():
    assert not needs_permission("read_file", {"path": "x"})
    assert not needs_permission("search_files", {"pattern": "x"})


def test_edit_diff_rejects_multiple_occurrences_with_line_numbers(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("aaa\nbbb\naaa\n")
    result = _edit_diff(str(f), "aaa", "c")
    assert isinstance(result, _DiffError)
    assert "lines 1, 3" in result


def test_edit_diff_allows_replace_all_for_multiple_occurrences(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("aaa\nbbb\naaa\n")
    result = _edit_diff(str(f), "aaa", "c", replace_all=True)
    assert not isinstance(result, _DiffError)
    assert result is not None


def test_dangerously_skip_permissions_bypasses_all_permission_checks():
    set_dangerously_skip_permissions(True)
    try:
        assert not needs_permission("run_command", {"command": "rm -rf /tmp/x"})
        assert not needs_permission("write_file", {"path": "x", "content": ""})
        assert not needs_permission("edit_file", {"path": "x", "old_string": "a", "new_string": "b"})
        # Bypass wins even over an explicit deny rule
        settings = Settings(permission_deny=("run_command(*)",))
        assert not needs_permission("run_command", {"command": "ls"}, settings=settings)
    finally:
        set_dangerously_skip_permissions(False)


def test_set_sandbox_toggles_is_sandbox():
    set_sandbox(True)
    try:
        assert is_sandbox() is True
    finally:
        set_sandbox(False)


class TestAllowDenyRules:
    def test_allow_pattern_skips_normally_gated_write(self):
        settings = Settings(permission_allow=("write_file(*)",))
        assert not needs_permission("write_file", {"path": "x", "content": ""}, settings=settings)

    def test_allow_pattern_is_scoped_to_its_glob(self):
        settings = Settings(permission_allow=("write_file(/tmp/*)",))
        assert needs_permission("write_file", {"path": "/etc/passwd", "content": ""}, settings=settings)

    def test_deny_pattern_forces_permission_on_benign_command(self):
        settings = Settings(permission_deny=("run_command(git push*)",))
        assert needs_permission("run_command", {"command": "git push origin main"}, settings=settings)

    def test_deny_wins_over_overlapping_allow(self):
        settings = Settings(
            permission_allow=("run_command(git *)",),
            permission_deny=("run_command(git push*)",),
        )
        assert needs_permission("run_command", {"command": "git push origin main"}, settings=settings)
        # Non-overlapping part of the allow pattern still skips the gate.
        assert not needs_permission("run_command", {"command": "git status"}, settings=settings)

    def test_no_rules_falls_back_to_existing_logic(self):
        settings = Settings()
        assert needs_permission("run_command", {"command": "rm -rf /tmp/x"}, settings=settings)
        assert not needs_permission("run_command", {"command": "ls -la"}, settings=settings)
        assert needs_permission("write_file", {"path": "x", "content": ""}, settings=settings)


class TestSuggestPattern:
    def test_run_command_scopes_to_the_program(self):
        assert _suggest_pattern("run_command", {"command": "git push origin main"}) == "run_command(git *)"

    def test_run_command_with_empty_command(self):
        assert _suggest_pattern("run_command", {"command": ""}) == "run_command(*)"

    def test_file_ops_scope_to_the_whole_tool(self):
        assert _suggest_pattern("write_file", {"path": "/tmp/x", "content": ""}) == "write_file(*)"
        assert _suggest_pattern("edit_file", {"path": "/tmp/x"}) == "edit_file(*)"


class TestAlwaysAllow:
    def test_always_choice_persists_pattern_and_approves(self, monkeypatch, tmp_path):
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(permissions, "_settings", Settings())
        monkeypatch.setattr(permissions, "persist_allow_pattern", lambda pattern, path=None: config_path.write_text(f'[permissions]\nallow = ["{pattern}"]\n'))
        monkeypatch.setattr(permissions, "_arrow_confirm", lambda: "always")

        result = request_permission("run_command", {"command": "git push origin main"})

        assert result is None
        assert "run_command(git *)" in permissions._settings.permission_allow
        assert "run_command(git *)" in config_path.read_text()

    def test_always_allow_skips_prompt_on_next_matching_call(self, monkeypatch, tmp_path):
        monkeypatch.setattr(permissions, "_settings", Settings())
        monkeypatch.setattr(permissions, "persist_allow_pattern", lambda pattern, path=None: None)
        monkeypatch.setattr(permissions, "_arrow_confirm", lambda: "always")

        request_permission("run_command", {"command": "git push origin main"})

        assert not needs_permission(
            "run_command", {"command": "git push origin feature"}, settings=permissions._settings
        )

    def test_yes_choice_approves_without_persisting(self, monkeypatch):
        monkeypatch.setattr(permissions, "_arrow_confirm", lambda: "yes")
        persisted = []
        monkeypatch.setattr(permissions, "persist_allow_pattern", lambda pattern, path=None: persisted.append(pattern))

        assert request_permission("run_command", {"command": "rm -rf /tmp/x"}) is None
        assert persisted == []

    def test_no_choice_cancels(self, monkeypatch):
        monkeypatch.setattr(permissions, "_arrow_confirm", lambda: "no")
        assert request_permission("run_command", {"command": "rm -rf /tmp/x"}) is not None
