from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.analysis import (
    ClarificationAnswerRequest,
    AnalysisRunCreateRequest,
    AnalysisRunListItem,
    AnalysisRunResponse,
    AnalysisRunReviewUpdateRequest,
)
from app.services.analysis_runs import AnalysisRunService

router = APIRouter()


@router.post("", response_model=AnalysisRunResponse, status_code=status.HTTP_201_CREATED)
def create_analysis_run(
    payload: AnalysisRunCreateRequest,
    db: Session = Depends(get_db),
) -> AnalysisRunResponse:
    service = AnalysisRunService(db)
    try:
        return service.create_run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[AnalysisRunListItem])
def list_analysis_runs(db: Session = Depends(get_db)) -> list[AnalysisRunListItem]:
    service = AnalysisRunService(db)
    return service.list_runs()


@router.get("/results", response_model=list[AnalysisRunListItem])
def list_analysis_results(db: Session = Depends(get_db)) -> list[AnalysisRunListItem]:
    service = AnalysisRunService(db)
    return service.list_results()


@router.get("/{analysis_run_id}", response_model=AnalysisRunResponse)
def get_analysis_run(
    analysis_run_id: UUID,
    db: Session = Depends(get_db),
) -> AnalysisRunResponse:
    service = AnalysisRunService(db)
    run = service.get_run(analysis_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run


@router.patch("/{analysis_run_id}/review", response_model=AnalysisRunResponse)
def update_analysis_run_review(
    analysis_run_id: UUID,
    payload: AnalysisRunReviewUpdateRequest,
    db: Session = Depends(get_db),
) -> AnalysisRunResponse:
    service = AnalysisRunService(db)
    run = service.update_review(analysis_run_id, payload)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run


@router.post("/{analysis_run_id}/clarifications", response_model=AnalysisRunResponse)
def answer_clarification(
    analysis_run_id: UUID,
    payload: ClarificationAnswerRequest,
    db: Session = Depends(get_db),
) -> AnalysisRunResponse:
    service = AnalysisRunService(db)
    try:
        run = service.answer_clarification(analysis_run_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return run
