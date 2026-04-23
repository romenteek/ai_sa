from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, case, func, literal, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.analysis import SourceReference


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    kind: str
    chunk_index: int
    text: str
    chunk_metadata: dict
    score: float

    def to_source_reference(self, rationale: str) -> SourceReference:
        return SourceReference(
            document_id=str(self.document_id),
            chunk_id=str(self.chunk_id),
            filename=self.filename,
            quote=self.text[:280],
            rationale=rationale,
        )


class RetrievalService:
    """Database-backed chunk retrieval.

    Text ranking is active in this milestone. Embedding/vector similarity remains
    a follow-up until robust embedding generation is wired into ingestion.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def search_chunks(
        self,
        *,
        query: str,
        document_ids: list[UUID] | None = None,
        document_kind: str | None = None,
        metadata_filters: dict[str, str] | None = None,
        limit: int = 6,
    ) -> list[RetrievedChunk]:
        normalized_query = " ".join(query.lower().split())
        tokens = [token for token in normalized_query.split(" ") if len(token) > 2]
        statement = self._base_statement(
            document_ids=document_ids or [],
            document_kind=document_kind,
            metadata_filters=metadata_filters or {},
        )

        if normalized_query:
            lowered_text = func.lower(DocumentChunk.text)
            score_expr = case((lowered_text.like(f"%{normalized_query}%"), 3.0), else_=0.0)
            for token in tokens:
                score_expr = score_expr + case(
                    (lowered_text.like(f"%{token}%"), 1.0),
                    else_=0.0,
                )
                score_expr = score_expr + (
                    (
                        func.length(lowered_text)
                        - func.length(func.replace(lowered_text, token, ""))
                    )
                    / max(len(token), 1)
                )
            statement = statement.add_columns(score_expr.label("score")).order_by(
                score_expr.desc(),
                Document.created_at.desc(),
                DocumentChunk.chunk_index.asc(),
            )
        else:
            statement = statement.add_columns(literal(0.0).label("score")).order_by(
                Document.created_at.desc(),
                DocumentChunk.chunk_index.asc(),
            )

        rows = self.db.execute(statement.limit(limit)).all()
        results = [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                filename=document.filename,
                kind=document.kind,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                chunk_metadata=chunk.chunk_metadata,
                score=float(score),
            )
            for document, chunk, score in rows
            if not normalized_query or float(score) > 0.0
        ]

        if results:
            return results

        fallback_rows = self.db.execute(
            self._base_statement(
                document_ids=document_ids or [],
                document_kind=document_kind,
                metadata_filters=metadata_filters or {},
            )
            .add_columns(literal(0.0).label("score"))
            .order_by(Document.created_at.desc(), DocumentChunk.chunk_index.asc())
            .limit(limit)
        ).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                filename=document.filename,
                kind=document.kind,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                chunk_metadata=chunk.chunk_metadata,
                score=float(score),
            )
            for document, chunk, score in fallback_rows
        ]

    @staticmethod
    def vector_search_enabled() -> bool:
        return False

    def _base_statement(
        self,
        *,
        document_ids: list[UUID],
        document_kind: str | None,
        metadata_filters: dict[str, str],
    ) -> Select[tuple[Document, DocumentChunk]]:
        statement = (
            select(Document, DocumentChunk)
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
        )
        if document_ids:
            statement = statement.where(Document.id.in_(document_ids))
        if document_kind:
            statement = statement.where(Document.kind == document_kind)
        for key, value in metadata_filters.items():
            statement = statement.where(Document.source_metadata[key].as_string() == str(value))
        return statement
