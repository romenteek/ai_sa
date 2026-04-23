from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    document_id: str | None = None
    chunk_id: str | None = None
    filename: str | None = None
    quote: str | None = None
    rationale: str | None = None


class GeneratedTaskPayload(BaseModel):
    title: str
    description: str
    why_needed: str
    service_or_component: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(default_factory=list)
    confidence: float = 0.0


class AnalysisOutput(BaseModel):
    feature_summary: str
    affected_components: list[str] = Field(default_factory=list)
    backend_tasks: list[GeneratedTaskPayload] = Field(default_factory=list)
    frontend_tasks: list[GeneratedTaskPayload] = Field(default_factory=list)
    integration_tasks: list[GeneratedTaskPayload] = Field(default_factory=list)
    db_changes: list[GeneratedTaskPayload] = Field(default_factory=list)
    qa_tasks: list[GeneratedTaskPayload] = Field(default_factory=list)
    observability_tasks: list[GeneratedTaskPayload] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    confidence: float = 0.0


class AnalysisRunCreateRequest(BaseModel):
    query: str = Field(
        default="Summarize the implementation work required by the selected documents.",
        min_length=1,
    )
    document_ids: list[UUID] = Field(default_factory=list)
    document_kind: str | None = None
    metadata_filters: dict[str, str] = Field(default_factory=dict)
    max_chunks: int = Field(default=6, ge=1, le=20)


class AnalysisRunResponse(AnalysisOutput):
    id: UUID
    status: str
    document_id: UUID | None = None
    request_payload: dict = Field(default_factory=dict)
    validation_notes: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}
