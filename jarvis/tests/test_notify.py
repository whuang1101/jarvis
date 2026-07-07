from jarvis import notify


def test_send_notification_uses_osascript(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.shutil, "which", lambda name: "/usr/bin/osascript" if name == "osascript" else None)
    monkeypatch.setattr(notify.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    notify.send_notification("Title", "Hello world")

    assert len(calls) == 1
    argv = calls[0][0][0]
    assert argv[:2] == ["osascript", "-e"]
    assert "Hello world" in argv[2]


def test_send_notification_falls_back_to_bell(monkeypatch, capsys):
    monkeypatch.setattr(notify.shutil, "which", lambda name: None)

    notify.send_notification("Title", "Hello world")

    captured = capsys.readouterr()
    assert "\a" in captured.err


def test_send_notification_swallows_subprocess_errors(monkeypatch):
    monkeypatch.setattr(notify.shutil, "which", lambda name: "/usr/bin/osascript" if name == "osascript" else None)

    def raise_error(*a, **k):
        raise OSError("boom")

    monkeypatch.setattr(notify.subprocess, "run", raise_error)

    notify.send_notification("Title", "Hello world")
