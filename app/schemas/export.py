from pydantic import BaseModel


class JiraExportRequest(BaseModel):
    analysis_run_id: str
    approved: bool = False


class JiraExportResponse(BaseModel):
    status: str
    message: str
