from jarvis.settings import Settings
from jarvis.tools.read_file import ReadFileTool


def test_image_path_attached_when_vision_enabled(tmp_path):
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\n")

    result = ReadFileTool().execute({"path": str(photo)})

    assert "attached below" in result


def test_image_path_notes_vision_disabled(tmp_path, monkeypatch):
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, *a, **k: Settings(vision=False)))

    result = ReadFileTool().execute({"path": str(photo)})

    assert "vision is disabled" in result


def test_image_path_missing_file(tmp_path):
    missing = tmp_path / "missing.png"

    result = ReadFileTool().execute({"path": str(missing)})

    assert result.startswith("Error: file not found")
