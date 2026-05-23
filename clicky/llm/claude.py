"""LLM client.

Note: file is named claude.py for historical reasons. It now talks to OpenAI's
Chat Completions API via the local/Cloudflare worker proxy. Class names
(ClaudeClient, ClaudeRequest, ...) are kept stable to avoid churn in state.py.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx


@dataclass
class LabeledImage:
    data: bytes
    label: str


@dataclass
class ConversationTurn:
    user_text: str
    assistant_text: str


@dataclass
class ClaudeRequest:
    user_prompt: str
    images: list[LabeledImage] = field(default_factory=list)
    history: list[ConversationTurn] = field(default_factory=list)


def _detect_image_media_type(image_data: bytes) -> str:
    if len(image_data) >= 4 and image_data[:4] == b"\x89PNG":
        return "image/png"
    return "image/jpeg"


def _build_messages(request: ClaudeRequest, system_prompt: str) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    for turn in request.history:
        messages.append({"role": "user", "content": turn.user_text})
        messages.append({"role": "assistant", "content": turn.assistant_text})

    content_blocks: list[dict] = []
    for image in request.images:
        media_type = _detect_image_media_type(image.data)
        b64 = base64.b64encode(image.data).decode("ascii")
        content_blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}"},
            }
        )
        content_blocks.append({"type": "text", "text": image.label})
    content_blocks.append({"type": "text", "text": request.user_prompt})

    messages.append({"role": "user", "content": content_blocks})
    return messages


class ClaudeClient:
    def __init__(
        self,
        endpoint_url: str,
        model: str,
        max_tokens: int = 1024,
        timeout: float = 120.0,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._model = model
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def stream_response(
        self,
        request: ClaudeRequest,
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """Yields cumulative text as the model streams its response via SSE.

        Each yielded value is the full accumulated text so far (not just the new delta),
        matching the original Swift `onTextChunk` semantics.
        """
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "stream": True,
            "messages": _build_messages(request, system_prompt),
        }

        accumulated = ""
        async with self._client.stream(
            "POST",
            self._endpoint_url,
            json=payload,
            headers={"content-type": "application/json"},
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                raise RuntimeError(
                    f"LLM API error {response.status_code}: {error_body.decode(errors='replace')}"
                )

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload_str = line[6:].strip()
                if payload_str == "[DONE]":
                    break
                if not payload_str:
                    continue
                try:
                    event = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue

                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text_chunk = delta.get("content")
                if not text_chunk:
                    continue
                accumulated += text_chunk
                yield accumulated
