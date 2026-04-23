from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.analysis import AnalysisRunCreateRequest, AnalysisRunResponse
from app.services.analysis_runs import AnalysisRunService

router = APIRouter()


@router.post("", response_model=AnalysisRunResponse, status_code=status.HTTP_201_CREATED)
def create_analysis_run(
    payload: AnalysisRunCreateRequest,
    db: Session = Depends(get_db),
) -> AnalysisRunResponse:
    service = AnalysisRunService(db)
    return service.create_run(payload)


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
