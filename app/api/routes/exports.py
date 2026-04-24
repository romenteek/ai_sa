from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.export import JiraExportPreviewRequest, JiraExportPreviewResponse, JiraExportRequest, JiraExportResponse
from app.services.exports import JiraExportError, JiraExportService

router = APIRouter()


@router.post("/jira/preview", response_model=JiraExportPreviewResponse)
def preview_jira_export(
    payload: JiraExportPreviewRequest,
    db: Session = Depends(get_db),
) -> JiraExportPreviewResponse:
    service = JiraExportService(db)
    try:
        return service.build_preview(payload)
    except JiraExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jira", response_model=JiraExportResponse)
def export_to_jira(
    payload: JiraExportRequest,
    db: Session = Depends(get_db),
) -> JiraExportResponse:
    service = JiraExportService(db)
    try:
        return service.execute_export(payload)
    except JiraExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
