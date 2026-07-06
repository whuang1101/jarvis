from __future__ import annotations

import jarvis.sessions as sessions_mod
from jarvis.sessions import SessionStore


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
