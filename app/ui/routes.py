from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.analysis import AnalysisRunCreateRequest, AnalysisRunReviewUpdateRequest
from app.services.analysis_runs import AnalysisRunService
from app.services.ingestion import IngestionService
from app.ui.rendering import (
    render_analysis_run_detail,
    render_analysis_runs_page,
    render_dashboard,
    render_document_detail,
    render_documents_page,
    render_new_analysis_page,
)


ui_router = APIRouter(include_in_schema=False)


@ui_router.get("/", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)) -> HTMLResponse:
    documents = IngestionService(db).list_documents()
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_dashboard(documents, runs))


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
    db: Session = Depends(get_db),
) -> HTMLResponse:
    documents = IngestionService(db).list_documents()
    return HTMLResponse(
        render_new_analysis_page(
            documents,
            selected_document_id=str(document_id) if document_id else None,
        )
    )


@ui_router.post("/analysis-runs")
def create_analysis_run_ui(
    query: str = Form(...),
    document_ids: list[UUID] = Form(default_factory=list),
    document_kind: str = Form(default=""),
    max_chunks: int = Form(default=6),
    db: Session = Depends(get_db),
) -> Response:
    documents = IngestionService(db).list_documents()
    payload = AnalysisRunCreateRequest(
        query=query,
        document_ids=document_ids,
        document_kind=document_kind or None,
        max_chunks=max_chunks,
    )
    try:
        run = AnalysisRunService(db).create_run(payload)
    except ValueError as exc:
        return HTMLResponse(
            render_new_analysis_page(documents, error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url=f"/analysis-runs/{run.id}", status_code=status.HTTP_303_SEE_OTHER)


@ui_router.get("/analysis-runs", response_class=HTMLResponse)
def analysis_runs_page(db: Session = Depends(get_db)) -> HTMLResponse:
    runs = AnalysisRunService(db).list_runs()
    return HTMLResponse(render_analysis_runs_page(runs))


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
