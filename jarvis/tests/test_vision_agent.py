from jarvis.images import is_image_path, image_message

_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415478da6360000002000155a0d3fb0000000049454e44ae426082"
)


def test_is_image_path_guard():
    assert is_image_path("pic.png") is True
    assert is_image_path("x.py") is False


def test_image_message_shape(tmp_path):
    path = tmp_path / "pic.png"
    path.write_bytes(_PNG_BYTES)
    msg = image_message(str(path))
    assert msg["role"] == "user"
    assert msg["content"][1]["type"] == "image_url"
