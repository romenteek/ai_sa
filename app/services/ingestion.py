from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentDetail, DocumentListItem
from app.services.chunking import chunk_text, enumerate_chunks
from app.services.storage import LocalStorage


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}


class IngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage = LocalStorage()

    async def ingest_upload(self, upload: UploadFile, kind: str) -> DocumentDetail:
        filename = upload.filename or "uploaded-document"
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_TEXT_EXTENSIONS:
            raise ValueError("Only .txt and .md uploads are supported in the current milestone.")

        storage_path, raw_content = await self.storage.save_upload(upload, subdir=kind)
        try:
            extracted_text = raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Uploaded file must be UTF-8 encoded text.") from exc

        chunk_defs = enumerate_chunks(
            chunk_text(
                text=extracted_text,
                max_chunk_size=self.settings.max_chunk_size,
                overlap=self.settings.chunk_overlap,
            )
        )

        document = Document(
            filename=filename,
            kind=kind,
            content_type=upload.content_type or "text/plain",
            storage_path=str(storage_path),
            checksum=self.storage.checksum(raw_content),
            source_metadata={"extension": suffix},
            extracted_text=extracted_text,
            chunk_count=len(chunk_defs),
        )

        document.chunks = [
            DocumentChunk(
                chunk_index=chunk_def["chunk_index"],
                text=chunk_def["text"],
                token_estimate=chunk_def["token_estimate"],
                chunk_metadata={"kind": kind, "filename": filename},
            )
            for chunk_def in chunk_defs
        ]

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return self._to_detail(document)

    def list_documents(self) -> list[DocumentListItem]:
        statement = select(Document).order_by(Document.created_at.desc())
        documents = self.db.scalars(statement).all()
        return [DocumentListItem.model_validate(document) for document in documents]

    def get_document(self, document_id: UUID) -> DocumentDetail | None:
        statement = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        document = self.db.scalars(statement).first()
        if document is None:
            return None
        return self._to_detail(document)

    @staticmethod
    def _to_detail(document: Document) -> DocumentDetail:
        return DocumentDetail.model_validate(document)
