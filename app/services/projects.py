from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.project import Project
from app.schemas.project import ProjectCreateRequest, ProjectListItem, ProjectResponse
from app.services.storage import LocalStorage


SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz"}


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = LocalStorage()

    async def create_project(
        self,
        payload: ProjectCreateRequest,
        archive: UploadFile | None = None,
    ) -> ProjectResponse:
        if payload.source_type == "github" and not payload.repository_url:
            raise ValueError("Repository URL is required for GitHub projects.")
        archive_reference = payload.archive_reference
        if payload.source_type == "archive":
            if archive is not None and archive.filename:
                suffix = "".join(Path(archive.filename).suffixes[-2:]).lower()
                simple_suffix = Path(archive.filename).suffix.lower()
                if suffix not in SUPPORTED_ARCHIVE_EXTENSIONS and simple_suffix not in SUPPORTED_ARCHIVE_EXTENSIONS:
                    raise ValueError("Project archive must be a .zip, .tar, .tar.gz, or .tgz file.")
                storage_path, _ = await self.storage.save_upload(archive, subdir="project-archives")
                archive_reference = str(storage_path)
            if not archive_reference:
                raise ValueError("Archive upload or archive reference is required for archive projects.")

        project = Project(
            name=payload.name.strip(),
            description=payload.description.strip(),
            source_type=payload.source_type,
            repository_url=payload.repository_url.strip() if payload.repository_url else None,
            archive_reference=archive_reference,
            ingestion_status="not_started",
            ingestion_note=(
                "Project source is recorded. Repository clone/archive indexing is an explicit future ingestion boundary."
            ),
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return ProjectResponse.model_validate(project)

    def list_projects(self) -> list[ProjectListItem]:
        statement = (
            select(Project, func.count(AnalysisRun.id))
            .outerjoin(AnalysisRun, AnalysisRun.project_id == Project.id)
            .group_by(Project.id)
            .order_by(Project.created_at.desc())
        )
        items: list[ProjectListItem] = []
        for project, analysis_count in self.db.execute(statement).all():
            data = ProjectResponse.model_validate(project).model_dump()
            items.append(ProjectListItem(**data, analysis_count=analysis_count))
        return items

    def get_project(self, project_id: UUID) -> ProjectResponse | None:
        project = self.db.get(Project, project_id)
        if project is None:
            return None
        return ProjectResponse.model_validate(project)
