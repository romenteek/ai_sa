from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ui.routes import ui_router


settings = get_settings()
configure_logging(settings.app_debug)

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.include_router(api_router, prefix="/api/v1")
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/healthz")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}
