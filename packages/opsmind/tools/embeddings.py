"""Deterministic local embeddings (+ optional OpenAI-compatible API)."""

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
        # mild tf weighting
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def local_embed_many(texts: Sequence[str], dim: int = EMBEDDING_DIM) -> list[list[float]]:
    return [local_embed(t, dim=dim) for t in texts]


async def openai_embed_many(
    texts: Sequence[str],
    *,
    api_key: str,
    api_base: str,
    model: str = "text-embedding-3-small",
    dim: int = EMBEDDING_DIM,
) -> list[list[float]]:
    """Call an OpenAI-compatible embeddings endpoint and truncate/pad to ``dim``."""
    if not api_key:
        raise ValueError("api_key is required for openai embeddings")
    base = api_base.rstrip("/")
    url = f"{base}/embeddings" if base else "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": list(texts)}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()["data"]
        data = sorted(data, key=lambda row: row["index"])
    out: list[list[float]] = []
    for row in data:
        vec = list(row["embedding"])
        if len(vec) > dim:
            vec = vec[:dim]
        elif len(vec) < dim:
            vec = vec + [0.0] * (dim - len(vec))
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed texts. Uses local hashing unless OPSMIND_EMBEDDING_PROVIDER=openai."""
    provider = (os.getenv("OPSMIND_EMBEDDING_PROVIDER") or "local").strip().lower()
    if provider == "openai":
        # Sync wrapper kept simple — prefer local for P2 demos/tests.
        raise RuntimeError(
            "OpenAI embeddings require async path; use local provider for CLI ingest "
            "or call openai_embed_many from async code."
        )
    return local_embed_many(texts)
