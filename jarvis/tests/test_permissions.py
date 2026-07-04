from __future__ import annotations

import pytest

from jarvis.permissions import needs_permission

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
