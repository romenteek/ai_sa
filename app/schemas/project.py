from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ProjectSourceType = Literal["github", "archive"]


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    source_type: ProjectSourceType
    repository_url: str | None = None
    archive_reference: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str = ""
    source_type: ProjectSourceType
    repository_url: str | None = None
    archive_reference: str | None = None
    ingestion_status: str
    ingestion_note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItem(ProjectResponse):
    analysis_count: int = 0
