from __future__ import annotations

from jarvis.images import (
    encode_image_data_url,
    image_content_part,
    image_message,
    is_image_path,
)


class TestIsImagePath:
    def test_recognises_image_extensions_case_insensitively(self):
        assert is_image_path("a/b/Photo.PNG") is True
        assert is_image_path("x.jpg") is True

    def test_rejects_non_image_extensions(self):
        assert is_image_path("notes.txt") is False


class TestImageEncoding:
    def test_encode_image_data_url(self, tmp_path):
        path = tmp_path / "tiny.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        url = encode_image_data_url(str(path))
        assert url.startswith("data:image/png;base64,")

    def test_image_content_part_matches_data_url(self, tmp_path):
        path = tmp_path / "tiny.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        url = encode_image_data_url(str(path))
        assert image_content_part(str(path))["image_url"]["url"] == url

    def test_image_message_shape(self, tmp_path):
        path = tmp_path / "tiny.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        message = image_message(str(path))
        assert message["role"] == "user"
        assert message["content"][0]["type"] == "text"
        assert message["content"][1]["type"] == "image_url"
