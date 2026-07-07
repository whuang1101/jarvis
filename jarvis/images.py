"""Image encoding helpers for attaching image files to model conversations."""

import base64

_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})

_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def is_image_path(path: str) -> bool:
    lowered = path.lower()
    return any(lowered.endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _mime_for(path: str) -> str:
    lowered = path.lower()
    for ext, mime in _MIME_TYPES.items():
        if lowered.endswith(ext):
            return mime
    return "application/octet-stream"


def encode_image_data_url(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{_mime_for(path)};base64,{b64}"


def image_content_part(path: str) -> dict:
    return {"type": "image_url", "image_url": {"url": encode_image_data_url(path)}}


def image_message(path: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": f"Here is the image {path}:"},
            image_content_part(path),
        ],
    }
