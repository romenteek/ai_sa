from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReviewStatus = Literal["draft", "reviewed", "approved", "rejected"]
TaskType = Literal["feature", "enhancement", "bug", "technical_task", "spike"]
InputType = Literal["text", "file"]
Language = Literal["en", "ru"]
AnalysisStatus = Literal[
    "draft",
    "needs_clarification",
    "clarification_answered",
    "ready_for_final_analysis",
    "completed",
]


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


class InitialAnalysisOutput(BaseModel):
    request_summary: str
    task_type: TaskType
    language: Language = "en"
    understood_scope: list[str] = Field(default_factory=list)
    suspected_affected_components: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    preliminary_assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class AnalysisRunCreateRequest(BaseModel):
    project_id: UUID
    task_type: TaskType
    input_type: InputType = "text"
    input_text: str = ""
    input_file_reference: str | None = None
    language: Language | None = None
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
    project_id: UUID | None = None
    project_name: str | None = None
    task_type: str = "feature"
    input_type: str = "text"
    input_text: str = ""
    input_file_reference: str | None = None
    language: Language = "en"
    review_status: ReviewStatus
    reviewer_note: str = ""
    document_id: UUID | None = None
    request_payload: dict = Field(default_factory=dict)
    clarification: InitialAnalysisOutput | None = None
    clarification_rounds: list["ClarificationRoundResponse"] = Field(default_factory=list)
    validation_notes: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisRunListItem(BaseModel):
    id: UUID
    status: str
    project_id: UUID | None = None
    project_name: str | None = None
    task_type: str = "feature"
    review_status: ReviewStatus
    reviewer_note: str = ""
    document_id: UUID | None = None
    feature_summary: str
    confidence: float = 0.0
    created_at: datetime


class AnalysisRunReviewUpdateRequest(BaseModel):
    review_status: ReviewStatus
    reviewer_note: str = Field(default="", max_length=4000)


class ClarificationRoundResponse(BaseModel):
    id: UUID
    round_index: int
    questions: list[str] = Field(default_factory=list)
    answers: str = ""
    created_at: datetime
    answered_at: datetime | None = None

    model_config = {"from_attributes": True}


class ClarificationAnswerRequest(BaseModel):
    answers: str = Field(min_length=1, max_length=8000)
