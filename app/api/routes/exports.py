from fastapi import APIRouter, HTTPException, status

from app.schemas.export import JiraExportRequest, JiraExportResponse

router = APIRouter()


@router.post("/jira", response_model=JiraExportResponse)
def export_to_jira(payload: JiraExportRequest) -> JiraExportResponse:
    if not payload.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira export is blocked until a human explicitly approves the analysis.",
        )

    return JiraExportResponse(
        status="stubbed",
        message="Jira export integration is intentionally disabled by default in this MVP.",
    )
