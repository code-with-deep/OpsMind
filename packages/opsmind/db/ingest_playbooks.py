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
from opsmind.db.seed import ensure_readonly_role
from opsmind.tools.embeddings import local_embed

DEFAULT_PLAYBOOKS_DIR = Path(__file__).resolve().parents[3] / "data" / "playbooks"


def _content_hash(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def chunk_markdown(content: str, *, max_chars: int = 900) -> list[str]:
    """Split on markdown headings, then pack into ~max_chars chunks."""
    parts = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
    sections = [p.strip() for p in parts if p.strip()]
    if not sections:
        sections = [content.strip()] if content.strip() else []

    chunks: list[str] = []
    buf = ""
    for section in sections:
        if not buf:
            buf = section
        elif len(buf) + 2 + len(section) <= max_chars:
            buf = f"{buf}\n\n{section}"
        else:
            chunks.append(buf)
            buf = section
        # Hard-split oversized sections
        while len(buf) > max_chars * 1.5:
            chunks.append(buf[:max_chars])
            buf = buf[max_chars:].lstrip()
    if buf:
        chunks.append(buf)
    return chunks


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").replace("_", " ").title()


def ingest_playbooks(
    session: Session,
    playbooks_dir: Path | None = None,
) -> dict[str, int]:
    root = playbooks_dir or Path(os.getenv("PLAYBOOKS_DIR", str(DEFAULT_PLAYBOOKS_DIR)))
    if not root.is_dir():
        raise FileNotFoundError(f"Playbooks directory not found: {root}")

    files = sorted(root.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No markdown playbooks in {root}")

    ingested_docs = 0
    ingested_chunks = 0

    for path in files:
        text_value = path.read_text(encoding="utf-8")
        doc_key = path.stem
        digest = _content_hash(text_value)
        title = _title_from_markdown(text_value, doc_key)

        existing = session.scalar(select(Document).where(Document.doc_key == doc_key))
        if existing and existing.content_hash == digest and existing.chunks:
            continue

        if existing:
            session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == existing.id)
            )
            existing.title = title
            existing.path = str(path)
            existing.content_hash = digest
            document = existing
        else:
            document = Document(
                id=uuid.uuid4(),
                doc_key=doc_key,
                title=title,
                path=str(path),
                content_hash=digest,
            )
            session.add(document)
            session.flush()

        chunks = chunk_markdown(text_value)
        for idx, chunk in enumerate(chunks):
            session.add(
                DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk,
                    embedding=local_embed(chunk),
                    token_count=len(chunk.split()),
                )
            )
            ingested_chunks += 1
        ingested_docs += 1

    session.commit()
    return {"documents": ingested_docs, "chunks": ingested_chunks, "files": len(files)}


def run_ingest() -> None:
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("DATABASE_URL_SYNC must be set")
    engine = create_engine(url, pool_pre_ping=True)
    # Ensure pgvector is available (migration should have created it).
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
