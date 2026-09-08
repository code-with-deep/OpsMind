"""RAG retriever over ingested playbook chunks (pgvector)."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from opsmind.db.memory_models import Document, DocumentChunk
from opsmind.domain.evidence import Evidence
from opsmind.grounding.registry import SourceIdRegistry, default_registry
from opsmind.guardrails.rag_sanitize import sanitize_rag_text
from opsmind.memory.persist import persist_tool_result
from opsmind.tools.embeddings import embed_one


class RagToolError(ValueError):
    """Controlled error for RAG tool failures."""


@dataclass
class RagHit:
    doc_id: str
    doc_key: str
    title: str
    chunk_index: int
    content: str
    score: float


@dataclass
class RagToolResult:
    evidence: Evidence
    hits: list[RagHit]
    source_id: str
    latency_ms: int
    tool_invocation_id: str | None
    finding_id: str | None


def _fingerprint(hits: list[RagHit]) -> str:
    payload = [
        {
            "doc_key": h.doc_key,
            "chunk_index": h.chunk_index,
            "score": round(h.score, 6),
        }
        for h in hits
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def retrieve_playbooks(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    min_score: float = 0.05,
) -> list[RagHit]:
    """Return top playbook chunks by cosine similarity (tenant-scoped)."""
    q = (query or "").strip()
    if not q:
        raise RagToolError("query must be a non-empty string")
    if top_k < 1 or top_k > 20:
        raise RagToolError("top_k must be between 1 and 20")

    vector = embed_one(q)
    embedding_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
    # pgvector cosine distance (`<=>`): smaller is closer. Convert to similarity.
    sql = text(
        """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.chunk_index,
            c.content,
            d.doc_key,
            d.title,
            1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.tenant_id = :tenant_id
        ORDER BY c.embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    rows = session.execute(
        sql,
        {"embedding": embedding_literal, "top_k": top_k, "tenant_id": str(tenant_id)},
    ).mappings().all()

    hits: list[RagHit] = []
    for row in rows:
        score = float(row["score"])
        if score < min_score:
            continue
        hits.append(
            RagHit(
                doc_id=str(row["document_id"]),
                doc_key=row["doc_key"],
                title=row["title"],
                chunk_index=int(row["chunk_index"]),
                content=sanitize_rag_text(row["content"] or ""),
                score=score,
            )
        )
    return hits


def run_rag_tool(
    *,
    query: str,
    owner_session: Session,
    tenant_id: uuid.UUID,
    investigation_id: uuid.UUID | None = None,
    top_k: int = 5,
    min_score: float = 0.01,
    registry: SourceIdRegistry | None = None,
    persist: bool = True,
) -> RagToolResult:
    started = time.perf_counter()
    hits = retrieve_playbooks(
        owner_session, tenant_id=tenant_id, query=query, top_k=top_k, min_score=min_score
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    source_id = f"rag_{uuid.uuid4().hex[:12]}"
    fp = _fingerprint(hits)

    if hits:
        top = hits[0]
        claim = (
            f"Top playbook hit for '{query}' is '{top.title}' "
            f"(doc_key={top.doc_key}, score={top.score:.3f})."
        )
        confidence = min(0.95, max(0.5, top.score))
        gaps: list[str] = []
    else:
        claim = f"No playbook chunks matched query '{query}' above score {min_score}."
        confidence = 0.2
        gaps = ["No retrieved playbook evidence."]

    evidence = Evidence(
        claim=claim,
        confidence=confidence,
        sources=[
            {
                "type": "rag_chunk",
                "doc_id": h.doc_id,
                "doc_key": h.doc_key,
                "title": h.title,
                "chunk_index": h.chunk_index,
                "score": h.score,
                "excerpt": h.content[:240],
            }
            for h in hits
        ],
        assumptions=["Playbooks were ingested into documents/document_chunks."],
        gaps=gaps,
        source_id=source_id,
    )

    reg = registry or default_registry
    reg.register(
        source_id,
        kind="rag",
        ref={"query": query, "hit_count": len(hits), "fingerprint": fp},
    )

    invocation_id: str | None = None
    finding_id: str | None = None
    if persist:
        inv, finding = persist_tool_result(
            owner_session,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            tool_name="rag",
            template_key=None,
            request={"query": query, "top_k": top_k, "min_score": min_score},
            response_meta={
                "hits": [
                    {
                        "doc_key": h.doc_key,
                        "title": h.title,
                        "chunk_index": h.chunk_index,
                        "score": h.score,
                    }
                    for h in hits
                ]
            },
            result_fingerprint=fp,
            row_count=len(hits),
            latency_ms=latency_ms,
            source_id=source_id,
            evidence=evidence,
        )
        invocation_id = str(inv.id)
        finding_id = str(finding.id)

    return RagToolResult(
        evidence=evidence,
        hits=hits,
        source_id=source_id,
        latency_ms=latency_ms,
        tool_invocation_id=invocation_id,
        finding_id=finding_id,
    )


def count_documents(session: Session) -> int:
    return len(session.scalars(select(Document)).all())
