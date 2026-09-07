"""Deterministic local embeddings (+ OpenAI text-embedding-3-small)."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Sequence

import httpx

from opsmind.db.memory_models import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def local_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Hashing-trick bag-of-words embedding, L2-normalized.

    Stable across processes — enough for a small playbook corpus without an API key.
    """
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        vec[0] = 1.0
        return vec

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def local_embed_many(texts: Sequence[str], dim: int = EMBEDDING_DIM) -> list[list[float]]:
    return [local_embed(t, dim=dim) for t in texts]


def _normalize_to_dim(vec: list[float], dim: int) -> list[float]:
    if len(vec) > dim:
        vec = vec[:dim]
    elif len(vec) < dim:
        vec = vec + [0.0] * (dim - len(vec))
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _openai_request_embeddings(
    texts: Sequence[str],
    *,
    api_key: str,
    api_base: str,
    model: str,
    dim: int,
) -> list[list[float]]:
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when OPSMIND_EMBEDDING_PROVIDER=openai")
    if not texts:
        return []
    base = (api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # text-embedding-3-* supports Matryoshka `dimensions` so we keep EMBEDDING_DIM=384.
    payload = {
        "model": model,
        "input": list(texts),
        "dimensions": dim,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()["data"]
    data = sorted(data, key=lambda row: row["index"])
    return [_normalize_to_dim(list(row["embedding"]), dim) for row in data]


def openai_embed_many(
    texts: Sequence[str],
    *,
    api_key: str,
    api_base: str,
    model: str = "text-embedding-3-small",
    dim: int = EMBEDDING_DIM,
) -> list[list[float]]:
    """Sync OpenAI-compatible embeddings sized to ``dim`` (default 384)."""
    return _openai_request_embeddings(
        texts, api_key=api_key, api_base=api_base, model=model, dim=dim
    )


async def openai_embed_many_async(
    texts: Sequence[str],
    *,
    api_key: str,
    api_base: str,
    model: str = "text-embedding-3-small",
    dim: int = EMBEDDING_DIM,
) -> list[list[float]]:
    """Async variant for callers that already run in an event loop."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when OPSMIND_EMBEDDING_PROVIDER=openai")
    if not texts:
        return []
    base = (api_base or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": list(texts), "dimensions": dim}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()["data"]
    data = sorted(data, key=lambda row: row["index"])
    return [_normalize_to_dim(list(row["embedding"]), dim) for row in data]


def embedding_provider() -> str:
    return (os.getenv("OPSMIND_EMBEDDING_PROVIDER") or "local").strip().lower()


def embed_texts(texts: Sequence[str], dim: int = EMBEDDING_DIM) -> list[list[float]]:
    """Embed texts using local hashing (default) or OpenAI when configured."""
    provider = embedding_provider()
    if provider == "openai":
        return openai_embed_many(
            texts,
            api_key=(os.getenv("OPENAI_API_KEY") or "").strip(),
            api_base=(os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1").strip(),
            model=(os.getenv("OPSMIND_EMBEDDING_MODEL") or "text-embedding-3-small").strip(),
            dim=dim,
        )
    return local_embed_many(texts, dim=dim)


def embed_one(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    return embed_texts([text], dim=dim)[0]
