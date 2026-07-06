from __future__ import annotations

import fnmatch
import os

_SENSITIVE_GLOBS = (
    ".env", ".env.*", "*.pem", "*.key", "id_rsa", "id_dsa",
    "id_ecdsa", "id_ed25519", "*.p12", "*.pfx", "credentials", ".netrc",
    ".pgpass", "*.keystore",
)


def is_sensitive_path(path: str) -> bool:
    try:
        name = os.path.basename(path.rstrip("/")).lower()
        return any(fnmatch.fnmatch(name, glob) for glob in _SENSITIVE_GLOBS)
    except Exception:
        return False


def sensitive_read_error(path: str) -> str:
    return (
        f"Error: refusing to read sensitive file {path} — it matches a secret-file "
        "pattern. Enable dangerously_skip_permissions to override."
    )
