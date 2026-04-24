from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.analysis import ReviewStatus, SourceReference


ExportMode = Literal["dry_run", "live"]
ExportStatus = Literal["preview", "dry_run", "exported"]


class JiraExportPreviewRequest(BaseModel):
    analysis_run_id: UUID
    project_key: str | None = None
    issue_type: str | None = None


class JiraExportRequest(JiraExportPreviewRequest):
    confirm: bool = False


class JiraExportPayload(BaseModel):
    project_key: str
    issue_type: str
    summary: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    confidence: float = 0.0
    review_status: ReviewStatus
    reviewer_note: str = ""


class JiraExportPreviewResponse(BaseModel):
    status: Literal["preview"] = "preview"
    export_allowed: bool
    export_mode: ExportMode
    analysis_run_id: UUID
    message: str
    payload: JiraExportPayload
    jira_payload: dict
    missing_configuration: list[str] = Field(default_factory=list)


class JiraExportResponse(BaseModel):
    status: ExportStatus
    export_allowed: bool
    export_mode: ExportMode
    analysis_run_id: UUID
    message: str
    payload: JiraExportPayload
    jira_payload: dict
    issue_key: str | None = None
    issue_url: str | None = None
    missing_configuration: list[str] = Field(default_factory=list)
