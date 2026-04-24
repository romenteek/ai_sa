from fastapi import APIRouter

from app.api.routes import analysis_runs, documents, exports, health, projects


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(analysis_runs.router, prefix="/analysis-runs", tags=["analysis-runs"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
