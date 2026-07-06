from __future__ import annotations

import jarvis.sessions as sessions_mod
from jarvis.sessions import SessionStore, list_sessions


class TestSessionStore:
    def test_save_load_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", tmp_path)
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        store = SessionStore(cwd="/some/project")
        store.save(history)

        loaded_store, loaded_history = SessionStore.load(store.session_id)
        assert loaded_history == history
        assert loaded_store.cwd == "/some/project"
        assert loaded_store.first_message == "hello"
        assert loaded_store.session_id == store.session_id

    def test_session_id_has_timestamp_and_suffix(self):
        store = SessionStore(cwd="/x")
        assert "-" in store.session_id
        timestamp, suffix = store.session_id.rsplit("-", 1)
        assert len(suffix) == 6
        assert len(timestamp) == len("20260706-153000")

    def test_first_message_defaults_to_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", tmp_path)
        store = SessionStore(cwd="/x")
        store.save([{"role": "assistant", "content": "no user turn yet"}])

        _, loaded_history = SessionStore.load(store.session_id)
        assert loaded_history == [{"role": "assistant", "content": "no user turn yet"}]

    def test_creates_sessions_dir_if_missing(self, tmp_path, monkeypatch):
        target = tmp_path / "nested" / "sessions"
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", target)
        store = SessionStore(cwd="/x")
        store.save([{"role": "user", "content": "hi"}])
        assert (target / f"{store.session_id}.json").exists()


class TestListSessions:
    def test_empty_when_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", tmp_path / "missing")
        assert list_sessions() == []

    def test_newest_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", tmp_path)
        older = SessionStore(cwd="/proj", session_id="20260101-100000-aaaaaa")
        older.save([{"role": "user", "content": "first session"}])
        newer = SessionStore(cwd="/proj", session_id="20260202-100000-bbbbbb")
        newer.save([{"role": "user", "content": "second session"}])

        results = list_sessions()
        assert [r["session_id"] for r in results] == [newer.session_id, older.session_id]
        assert results[0]["first_message"] == "second session"

    def test_filters_by_cwd(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", tmp_path)
        SessionStore(cwd="/proj-a", session_id="20260101-100000-aaaaaa").save(
            [{"role": "user", "content": "a"}]
        )
        SessionStore(cwd="/proj-b", session_id="20260101-100001-bbbbbb").save(
            [{"role": "user", "content": "b"}]
        )

        results = list_sessions(cwd="/proj-b")
        assert len(results) == 1
        assert results[0]["cwd"] == "/proj-b"

    def test_respects_limit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sessions_mod, "_SESSIONS_DIR", tmp_path)
        for i in range(5):
            SessionStore(cwd="/proj", session_id=f"2026010{i}-100000-aaaaaa").save(
                [{"role": "user", "content": f"msg {i}"}]
            )

        assert len(list_sessions(limit=3)) == 3
