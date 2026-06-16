from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REQUIRED = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION")

# Candidate .env locations searched in order (first found wins)
_ENV_CANDIDATES = [
    Path.cwd() / ".env",
    Path.home() / ".jarvis.env",
    Path.home() / "jarvis" / ".env",
    Path(__file__).parent.parent / ".env",  # project root when installed editable
]


@dataclass(frozen=True)
class Config:
    endpoint: str
    api_key: str
    deployment: str
    api_version: str

    @classmethod
    def load(cls) -> "Config":
        for candidate in _ENV_CANDIDATES:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
        missing = [k for k in _REQUIRED if not os.getenv(k)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Check your .env file."
            )
        return cls(
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
