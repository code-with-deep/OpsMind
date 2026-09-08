"""Ingest playbook markdown into documents + pgvector chunks."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from opsmind.db.memory_models import Document, DocumentChunk
from opsmind.db import tenant_models as _tenant_models  # noqa: F401
from opsmind.db.seed import DEMO_TENANT_ID, ensure_readonly_role
from opsmind.tools.embeddings import embed_texts

DEFAULT_PLAYBOOKS_DIR = Path(__file__).resolve().parents[3] / "data" / "playbooks"
DEFAULT_UPLOADS_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"

# MT3 target: heading-aware chunks in the 512–768 token band with ~10–15% overlap.
_CHUNK_MIN_TOKENS = 512
_CHUNK_MAX_TOKENS = 768
_CHUNK_OVERLAP_RATIO = 0.12


def _content_hash(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def approx_token_count(text: str) -> int:
    """Rough token estimate without tiktoken (~4 chars / token)."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


def _resolve_tenant_id(session: Session, tenant_id: uuid.UUID | None) -> uuid.UUID:
    if tenant_id is not None:
        return tenant_id
    row = session.execute(
        text("SELECT id FROM tenants WHERE slug = 'demo' LIMIT 1")
    ).scalar()
    if row is not None:
        return uuid.UUID(str(row))
    return DEMO_TENANT_ID


def _overlap_prefix(previous: str, *, max_tokens: int, overlap_ratio: float) -> str:
    if not previous or overlap_ratio <= 0:
        return ""
    budget = max(1, int(max_tokens * overlap_ratio))
    words = previous.split()
    if not words:
        return ""
    # Take trailing words until approximate token budget is hit.
    taken: list[str] = []
    for word in reversed(words):
        candidate = " ".join([word, *reversed(taken)]) if taken else word
        if approx_token_count(candidate) > budget and taken:
            break
        taken.insert(0, word)
    return " ".join(taken).strip()


def chunk_markdown(
    content: str,
    *,
    min_tokens: int = _CHUNK_MIN_TOKENS,
    max_tokens: int = _CHUNK_MAX_TOKENS,
    overlap_ratio: float = _CHUNK_OVERLAP_RATIO,
) -> list[str]:
    """Heading-aware chunking targeting 512–768 tokens with overlap.

    Short documents remain a single chunk (no padding). Oversized sections are
    hard-split on word boundaries with overlap between consecutive pieces.
    """
    parts = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
    sections = [p.strip() for p in parts if p.strip()]
    if not sections:
        sections = [content.strip()] if content.strip() else []
    if not sections:
        return []

    chunks: list[str] = []
    buf = ""

    def flush(buf_value: str) -> str:
        text_value = buf_value.strip()
        if not text_value:
            return ""
        chunks.append(text_value)
        return _overlap_prefix(
            text_value, max_tokens=max_tokens, overlap_ratio=overlap_ratio
        )

    def hard_split_oversized(buf_value: str) -> str:
        current = buf_value.strip()
        while approx_token_count(current) > max_tokens:
            words = current.split()
            if len(words) <= 1:
                chunks.append(current)
                return ""
            # Keep each piece near max_tokens using char/token estimate.
            target_chars = max_tokens * 4
            cut = 1
            acc = 0
            for i, word in enumerate(words):
                acc += len(word) + (1 if i else 0)
                cut = i + 1
                if acc >= target_chars and i + 1 < len(words):
                    break
            if cut >= len(words):
                cut = max(1, len(words) // 2)
            head = " ".join(words[:cut]).strip()
            overlap = flush(head)
            rest = " ".join(words[cut:]).strip()
            current = f"{overlap}\n\n{rest}".strip() if overlap else rest
        return current

    for section in sections:
        if not buf:
            buf = section
        elif approx_token_count(f"{buf}\n\n{section}") <= max_tokens:
            buf = f"{buf}\n\n{section}"
        elif approx_token_count(buf) < (min_tokens // 2):
            # Tiny heading stub — attach to next section and hard-split later.
            buf = f"{buf}\n\n{section}"
        else:
            overlap = flush(buf)
            buf = f"{overlap}\n\n{section}".strip() if overlap else section
        buf = hard_split_oversized(buf)

    if buf.strip():
        # Prefer merging a trailing undersized fragment into the previous chunk
        # when it still fits under max_tokens.
        if (
            chunks
            and approx_token_count(buf) < min_tokens
            and approx_token_count(f"{chunks[-1]}\n\n{buf}") <= max_tokens
        ):
            chunks[-1] = f"{chunks[-1]}\n\n{buf.strip()}"
        else:
            chunks.append(buf.strip())
    return chunks


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").replace("_", " ").title()


def safe_doc_key(raw: str) -> str:
    """Normalize a filename / title into a stable doc_key."""
    stem = Path(raw).stem if raw else "playbook"
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip("-._").lower()
    return (cleaned or "playbook")[:120]


def tenant_playbook_path(tenant_id: uuid.UUID, doc_key: str) -> Path:
    root = Path(os.getenv("UPLOADS_DIR", str(DEFAULT_UPLOADS_DIR)))
    return root / str(tenant_id) / "playbooks" / f"{doc_key}.md"


def ingest_playbook_markdown(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    content: str,
    doc_key: str | None = None,
    path: str | None = None,
    title: str | None = None,
    commit: bool = True,
) -> tuple[Document, int]:
    """Upsert one playbook document + chunks for a tenant (MT3 upload path)."""
    text_value = content if content is not None else ""
    if not text_value.strip():
        raise ValueError("Playbook content is empty")

    key = safe_doc_key(doc_key or "playbook")
    digest = _content_hash(text_value)
    resolved_title = title or _title_from_markdown(text_value, key)
    resolved_path = path or str(tenant_playbook_path(tenant_id, key))

    existing = session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.doc_key == key)
    )
    if existing and existing.content_hash == digest and existing.chunks:
        return existing, len(existing.chunks)

    if existing:
        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == existing.id))
        existing.title = resolved_title
        existing.path = resolved_path
        existing.content_hash = digest
        document = existing
    else:
        document = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            doc_key=key,
            title=resolved_title,
            path=resolved_path,
            content_hash=digest,
        )
        session.add(document)
        session.flush()

    chunks = chunk_markdown(text_value)
    if not chunks:
        raise ValueError("Playbook produced no chunks")

    vectors = embed_texts(chunks)
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        session.add(
            DocumentChunk(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document.id,
                chunk_index=idx,
                content=chunk,
                embedding=vector,
                token_count=approx_token_count(chunk),
            )
        )

    if commit:
        session.commit()
        session.refresh(document)
    else:
        session.flush()
    return document, len(chunks)


def ingest_playbooks(
    session: Session,
    playbooks_dir: Path | None = None,
    tenant_id: uuid.UUID | None = None,
) -> dict[str, int]:
    root = playbooks_dir or Path(os.getenv("PLAYBOOKS_DIR", str(DEFAULT_PLAYBOOKS_DIR)))
    if not root.is_dir():
        raise FileNotFoundError(f"Playbooks directory not found: {root}")

    files = sorted(root.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No markdown playbooks in {root}")

    resolved_tenant = _resolve_tenant_id(session, tenant_id)
    ingested_docs = 0
    ingested_chunks = 0

    for path in files:
        text_value = path.read_text(encoding="utf-8")
        before = session.scalar(
            select(Document).where(
                Document.tenant_id == resolved_tenant,
                Document.doc_key == path.stem,
            )
        )
        skip = (
            before is not None
            and before.content_hash == _content_hash(text_value)
            and bool(before.chunks)
        )
        if skip:
            continue

        _doc, n_chunks = ingest_playbook_markdown(
            session,
            tenant_id=resolved_tenant,
            content=text_value,
            doc_key=path.stem,
            path=str(path),
            commit=False,
        )
        ingested_docs += 1
        ingested_chunks += n_chunks

    session.commit()
    return {"documents": ingested_docs, "chunks": ingested_chunks, "files": len(files)}


def delete_playbook(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    commit: bool = True,
) -> bool:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    if document is None:
        return False
    path = Path(document.path) if document.path else None
    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    session.delete(document)
    if commit:
        session.commit()
    if path and path.is_file() and "uploads" in path.as_posix():
        try:
            path.unlink()
        except OSError:
            pass
    return True


def run_ingest() -> None:
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("DATABASE_URL_SYNC must be set")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    with SessionLocal() as session:
        stats = ingest_playbooks(session)
    ensure_readonly_role(engine)
    print(
        f"Ingested playbooks: files={stats['files']} "
        f"updated_docs={stats['documents']} chunks={stats['chunks']}"
    )


if __name__ == "__main__":
    run_ingest()
