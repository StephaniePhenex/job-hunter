"""FastAPI application entrypoint."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import setup_logging
from app.core.schema_upgrade import upgrade_job_table
from app.core.scheduler import shutdown_scheduler, start_scheduler
from app.api.routes import jobs as jobs_routes
from app.models import AppliedUrl  # noqa: F401 — register model for create_all
from app.services.pipeline import get_pipeline_state, run_full_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and start background scheduler."""
    settings = get_settings()
    setup_logging(settings.log_level)
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    upgrade_job_table(engine)
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Intern Opportunity Intelligence Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # credentials=True + origins=* is rejected by browsers (CORS spec)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_routes.router, prefix="/jobs", tags=["jobs"])

STATIC_ROOT = Path(__file__).resolve().parent / "static"
if STATIC_ROOT.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_ROOT)),
        name="static",
    )


@app.get("/", response_model=None)
def index_page():
    """Serve minimal dashboard (Day 7 bonus)."""
    index = STATIC_ROOT / "index.html"
    if not index.is_file():
        return {"detail": "Dashboard not installed (missing app/static/index.html)."}
    return FileResponse(index)


@app.post("/run-scan")
def run_scan_root(background_tasks: BackgroundTasks) -> dict:
    """Spec alias: POST /run-scan — starts scan in background, returns immediately."""
    state = get_pipeline_state()
    if state["status"] == "running":
        return {
            "status": "already_running",
            "message": "A scan is already in progress.",
            "last_run_at": state["last_run_at"],
        }
    background_tasks.add_task(run_full_pipeline)
    return {"status": "queued", "message": "Scan started. Poll /scan-status for results."}


@app.get("/scan-status")
def scan_status_root() -> dict:
    """Pipeline status and last run result."""
    return get_pipeline_state()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
