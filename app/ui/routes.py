from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.analysis import AnalysisRunCreateRequest, AnalysisRunReviewUpdateRequest
from app.schemas.export import JiraExportPreviewRequest, JiraExportRequest
from app.schemas.project import ProjectCreateRequest
from app.services.analysis_runs import AnalysisRunService
from app.services.exports import JiraExportError, JiraExportService
from app.services.ingestion import IngestionService
from app.services.projects import ProjectService
from app.services.storage import LocalStorage
from app.ui.rendering import (
    render_analysis_run_detail,
    render_analysis_runs_page,
    render_clarifications_page,
    render_dashboard,
    render_document_detail,
    render_documents_page,
    render_export_preview_page,
    render_new_analysis_page,
    render_project_detail,
    render_projects_page,
    render_results_page,
)


ui_router = APIRouter(include_in_schema=False)


@ui_router.get("/", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)) -> HTMLResponse:
    documents = IngestionService(db).list_documents()
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_dashboard(documents, runs))


@ui_router.get("/projects", response_class=HTMLResponse)
def projects_page(db: Session = Depends(get_db)) -> HTMLResponse:
    projects = ProjectService(db).list_projects()
    return HTMLResponse(render_projects_page(projects))


@ui_router.post("/projects")
async def create_project_ui(
    name: str = Form(...),
    description: str = Form(default=""),
    source_type: str = Form(...),
    repository_url: str = Form(default=""),
    archive: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> Response:
    service = ProjectService(db)
    payload = ProjectCreateRequest(
        name=name,
        description=description,
        source_type=source_type,
        repository_url=repository_url or None,
    )
    try:
        project = await service.create_project(payload, archive=archive if archive and archive.filename else None)
    except ValueError as exc:
        projects = service.list_projects()
        return HTMLResponse(render_projects_page(projects, error=str(exc)), status_code=status.HTTP_400_BAD_REQUEST)
    return RedirectResponse(url=f"/projects/{project.id}", status_code=status.HTTP_303_SEE_OTHER)


@ui_router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(project_id: UUID, db: Session = Depends(get_db)) -> HTMLResponse:
    project_service = ProjectService(db)
    project = project_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_project_detail(project, runs))


@ui_router.get("/documents", response_class=HTMLResponse)
def documents_page(db: Session = Depends(get_db)) -> HTMLResponse:
    documents = IngestionService(db).list_documents()
    return HTMLResponse(render_documents_page(documents))


@ui_router.post("/documents/upload")
async def upload_document_ui(
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Response:
    service = IngestionService(db)
    try:
        document = await service.ingest_upload(upload=file, kind=kind)
    except ValueError as exc:
        documents = service.list_documents()
        return HTMLResponse(render_documents_page(documents, error=str(exc)), status_code=status.HTTP_400_BAD_REQUEST)

    return RedirectResponse(url=f"/documents/{document.id}", status_code=status.HTTP_303_SEE_OTHER)


@ui_router.get("/documents/{document_id}", response_class=HTMLResponse)
def document_detail(document_id: UUID, db: Session = Depends(get_db)) -> HTMLResponse:
    ingestion_service = IngestionService(db)
    document = ingestion_service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_document_detail(document, runs))


@ui_router.get("/analysis-runs/new", response_class=HTMLResponse)
def new_analysis_page(
    document_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    documents = IngestionService(db).list_documents()
    projects = ProjectService(db).list_projects()
    return HTMLResponse(
        render_new_analysis_page(
            documents,
            projects,
            selected_document_id=str(document_id) if document_id else None,
            selected_project_id=str(project_id) if project_id else None,
        )
    )


@ui_router.post("/analysis-runs")
async def create_analysis_run_ui(
    project_id: UUID = Form(...),
    task_type: str = Form(...),
    input_text: str = Form(default=""),
    input_file: UploadFile | None = File(default=None),
    query: str = Form(...),
    document_ids: list[UUID] = Form(default_factory=list),
    document_kind: str = Form(default=""),
    max_chunks: int = Form(default=6),
    db: Session = Depends(get_db),
) -> Response:
    documents = IngestionService(db).list_documents()
    projects = ProjectService(db).list_projects()
    input_file_reference = None
    input_type = "text"
    if input_file is not None and input_file.filename:
        storage_path, _ = await LocalStorage().save_upload(input_file, subdir="analysis-inputs")
        input_file_reference = str(storage_path)
        input_type = "file"
    payload = AnalysisRunCreateRequest(
        project_id=project_id,
        task_type=task_type,
        input_type=input_type,
        input_text=input_text,
        input_file_reference=input_file_reference,
        query=query,
        document_ids=document_ids,
        document_kind=document_kind or None,
        max_chunks=max_chunks,
    )
    try:
        run = AnalysisRunService(db).create_run(payload)
    except ValueError as exc:
        return HTMLResponse(
            render_new_analysis_page(documents, projects, error=str(exc), selected_project_id=str(project_id)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url=f"/analysis-runs/{run.id}", status_code=status.HTTP_303_SEE_OTHER)


@ui_router.get("/analysis-runs", response_class=HTMLResponse)
def analysis_runs_page(db: Session = Depends(get_db)) -> HTMLResponse:
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_analysis_runs_page(runs))


@ui_router.get("/clarifications", response_class=HTMLResponse)
def clarifications_page(db: Session = Depends(get_db)) -> HTMLResponse:
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_clarifications_page(runs))


@ui_router.get("/results", response_class=HTMLResponse)
def results_page(db: Session = Depends(get_db)) -> HTMLResponse:
    runs = AnalysisRunService(db).list_results()
    return HTMLResponse(render_results_page(runs))


@ui_router.get("/analysis-runs/{analysis_run_id}", response_class=HTMLResponse)
def analysis_run_detail(
    analysis_run_id: UUID,
    updated: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    run = AnalysisRunService(db).get_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    success = "Review status updated." if updated == "1" else None
    return HTMLResponse(render_analysis_run_detail(run, success=success))


@ui_router.post("/analysis-runs/{analysis_run_id}/clarifications")
def answer_clarification_ui(
    analysis_run_id: UUID,
    answers: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    from app.schemas.analysis import ClarificationAnswerRequest

    run = AnalysisRunService(db).answer_clarification(
        analysis_run_id,
        ClarificationAnswerRequest(answers=answers),
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return RedirectResponse(url=f"/analysis-runs/{analysis_run_id}", status_code=status.HTTP_303_SEE_OTHER)


@ui_router.get("/analysis-runs/{analysis_run_id}/export", response_class=HTMLResponse)
def analysis_run_export_preview(
    analysis_run_id: UUID,
    project_key: str | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    service = JiraExportService(db)
    try:
        preview = service.build_preview(
            JiraExportPreviewRequest(
                analysis_run_id=analysis_run_id,
                project_key=project_key,
                issue_type=issue_type,
            )
        )
    except JiraExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return HTMLResponse(render_export_preview_page(preview))


@ui_router.post("/analysis-runs/{analysis_run_id}/review")
def update_analysis_review_ui(
    analysis_run_id: UUID,
    review_status: str = Form(...),
    reviewer_note: str = Form(default=""),
    db: Session = Depends(get_db),
) -> Response:
    service = AnalysisRunService(db)
    payload = AnalysisRunReviewUpdateRequest(
        review_status=review_status,
        reviewer_note=reviewer_note,
    )
    run = service.update_review(analysis_run_id, payload)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return RedirectResponse(url=f"/analysis-runs/{analysis_run_id}?updated=1", status_code=status.HTTP_303_SEE_OTHER)


@ui_router.post("/analysis-runs/{analysis_run_id}/export")
def execute_export_ui(
    analysis_run_id: UUID,
    project_key: str = Form(default=""),
    issue_type: str = Form(default=""),
    confirm: str = Form(default=""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    service = JiraExportService(db)
    preview_request = JiraExportPreviewRequest(
        analysis_run_id=analysis_run_id,
        project_key=project_key or None,
        issue_type=issue_type or None,
    )
    preview = service.build_preview(preview_request)

    try:
        result = service.execute_export(
            JiraExportRequest(
                analysis_run_id=analysis_run_id,
                project_key=project_key or None,
                issue_type=issue_type or None,
                confirm=confirm.lower() == "true",
            )
        )
    except JiraExportError as exc:
        return HTMLResponse(
            render_export_preview_page(preview, error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return HTMLResponse(render_export_preview_page(preview, result=result))
