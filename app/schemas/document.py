from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChunkPreview(BaseModel):
    id: UUID
    chunk_index: int
    text: str
    token_estimate: int
    chunk_metadata: dict

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: UUID
    filename: str
    kind: str
    content_type: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentListItem):
    storage_path: str
    source_metadata: dict
    extracted_text: str
    chunks: list[ChunkPreview]

    model_config = {"from_attributes": True}
