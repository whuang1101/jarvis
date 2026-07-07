from __future__ import annotations

import subprocess

from jarvis import checkpoints
from jarvis.context import ContextManager


def teardown_function(_fn) -> None:
    checkpoints.clear()


def test_create_returns_incrementing_index() -> None:
    assert checkpoints.create([{"role": "user", "content": "a"}]) == 1
    assert checkpoints.create([{"role": "user", "content": "b"}]) == 2


def test_get_round_trips_history_and_is_isolated() -> None:
    history = [{"role": "user", "content": "a"}]
    checkpoints.create(history)
    first = checkpoints.get(1)
    assert first is not None
    assert first["history"] == history

    first["history"].append({"role": "assistant", "content": "mutated"})
    first["history"][0]["content"] = "mutated"

    second = checkpoints.get(1)
    assert second is not None
    assert second["history"] == [{"role": "user", "content": "a"}]


def test_mutating_input_after_create_does_not_affect_stored_checkpoint() -> None:
    history = [{"role": "user", "content": "a"}]
    checkpoints.create(history)
    history.append({"role": "user", "content": "extra"})
    history[0]["content"] = "changed"

    stored = checkpoints.get(1)
    assert stored is not None
    assert stored["history"] == [{"role": "user", "content": "a"}]


def test_get_out_of_range_returns_none() -> None:
    checkpoints.create([{"role": "user", "content": "a"}])
    assert checkpoints.get(0) is None
    assert checkpoints.get(2) is None


def test_list_checkpoints_has_metadata_but_no_history() -> None:
    checkpoints.create([{"role": "user", "content": "a"}], label="hello", file_stash="stash-1")
    entries = checkpoints.list_checkpoints()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["label"] == "hello"
    assert "time" in entry
    assert entry["has_files"] is True
    assert "history" not in entry


def test_list_checkpoints_has_files_false_without_stash() -> None:
    checkpoints.create([{"role": "user", "content": "a"}])
    assert checkpoints.list_checkpoints()[0]["has_files"] is False


def test_trims_to_max_checkpoints_dropping_oldest() -> None:
    for i in range(checkpoints._MAX_CHECKPOINTS + 5):
        checkpoints.create([{"role": "user", "content": str(i)}])
    entries = checkpoints.list_checkpoints()
    assert len(entries) == checkpoints._MAX_CHECKPOINTS
    oldest_kept = checkpoints.get(1)
    assert oldest_kept is not None
    assert oldest_kept["history"] == [{"role": "user", "content": "5"}]


def test_clear_and_summary() -> None:
    checkpoints.create([{"role": "user", "content": "a"}])
    checkpoints.clear()
    assert checkpoints.list_checkpoints() == []
    assert checkpoints.summary() == ""


def test_summary_nonempty() -> None:
    checkpoints.create([{"role": "user", "content": "a"}])
    checkpoints.create([{"role": "user", "content": "b"}])
    assert checkpoints.summary() == "2 checkpoints"


def test_snapshot_and_restore_files_round_trip(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, text=True, check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("original\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, text=True, check=True)

    tracked.write_text("modified\n")
    sha = checkpoints.snapshot_files(cwd=str(repo))
    assert sha is not None
    assert len(sha) == 40

    subprocess.run(["git", "checkout", "--", "tracked.txt"], cwd=repo, capture_output=True, text=True, check=True)
    assert tracked.read_text() == "original\n"

    result = checkpoints.restore_files(sha, cwd=str(repo))
    assert result == "Files restored from checkpoint."
    assert tracked.read_text() == "modified\n"


def test_snapshot_files_returns_none_outside_git_repo(tmp_path) -> None:
    assert checkpoints.snapshot_files(cwd=str(tmp_path)) is None


def test_checkpoint_turn_snapshots_history_before_new_message() -> None:
    ctx = ContextManager()
    ctx.append({"role": "user", "content": "first"})

    index = checkpoints.checkpoint_turn(ctx, "hi")
    assert index == 1
    stored = checkpoints.get(1)
    assert stored is not None
    assert stored["label"] == "hi"
    assert len(stored["history"]) == 1

    ctx.append({"role": "user", "content": "second"})
    index = checkpoints.checkpoint_turn(ctx, "again")
    assert index == 2
    stored = checkpoints.get(2)
    assert stored is not None
    assert len(stored["history"]) == 2
