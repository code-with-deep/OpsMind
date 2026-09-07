"""Memory / investigation persistence models (P2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opsmind.db.base import Base

# Local hashing embeddings use a fixed dimension (no external API required for P2).
EMBEDDING_DIM = 384


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    window_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    window_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plan: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    hypothesis: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    critique: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audit: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    events: Mapped[list[InvestigationEvent]] = relationship(back_populates="investigation")
    tool_invocations: Mapped[list[ToolInvocation]] = relationship(
        back_populates="investigation"
    )
    findings: Mapped[list[Finding]] = relationship(back_populates="investigation")
    reviews: Mapped[list[Review]] = relationship(back_populates="investigation")
    case_summary: Mapped[Optional[CaseSummary]] = relationship(
        back_populates="investigation", uselist=False
    )


class InvestigationEvent(Base):
    __tablename__ = "investigation_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="events")


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_id", name="uq_tool_invocations_tenant_source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    response_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    investigation: Mapped[Optional[Investigation]] = relationship(
        back_populates="tool_invocations"
    )
    findings: Mapped[list[Finding]] = relationship(back_populates="tool_invocation")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=True, index=True
    )
    tool_invocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_invocations.id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sources: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    assumptions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    gaps: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    investigation: Mapped[Optional[Investigation]] = relationship(back_populates="findings")
    tool_invocation: Mapped[ToolInvocation] = relationship(back_populates="findings")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("tenant_id", "doc_key", name="uq_documents_tenant_doc_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class Review(Base):
    """Operator decision / review for an investigation (P6)."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "approved", "rejected", "comment"
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="reviews")
    case_summary: Mapped[Optional[CaseSummary]] = relationship(
        back_populates="review", uselist=False
    )


class CaseSummary(Base):
    """Case memory entry promoted upon operator approval (P6)."""

    __tablename__ = "case_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    review_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    drivers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    actions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="case_summary")
    review: Mapped[Optional[Review]] = relationship(back_populates="case_summary")

