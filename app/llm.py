from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from app.config import settings


def _client() -> OpenAI:
    if not settings.openai_api_key and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing.")
    return OpenAI()


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = _client()
    resp = client.embeddings.create(model=settings.openai_embed_model, input=texts)
    return [d.embedding for d in resp.data]


def chat_completion(messages: list[dict[str, Any]]) -> str:
    client = _client()
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""

