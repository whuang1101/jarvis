from __future__ import annotations

from collections.abc import Iterator
from typing import Any, NamedTuple, cast

from openai import AzureOpenAI
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

from .config import Config


class CompleteResult(NamedTuple):
    text: str
    prompt_tokens: int
    completion_tokens: int


class JarvisClient:
    def __init__(self, config: Config) -> None:
        self._client = AzureOpenAI(
            azure_endpoint=config.endpoint,
            api_key=config.api_key,
            api_version=config.api_version,
        )
        self._deployment = config.deployment

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[ChatCompletionChunk]:
        kwargs: dict[str, Any] = {
            "model": self._deployment,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self._client.chat.completions.create(**kwargs)

    def current_deployment(self) -> str:
        return self._deployment

    def set_deployment(self, deployment: str) -> None:
        self._deployment = deployment

    def complete(
        self,
        messages: list[dict[str, Any]],
    ) -> CompleteResult:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=cast(list[ChatCompletionMessageParam], messages),
            stream=False,
        )
        usage = response.usage
        return CompleteResult(
            text=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
