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
from app.api.routes import analyze as analyze_routes
from app.api.routes import optimize as optimize_routes
from app.models import AppliedUrl, JobAnalysis  # noqa: F401 — register models for create_all
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
app.include_router(analyze_routes.router, prefix="/api/analyze", tags=["analyze"])
app.include_router(optimize_routes.router, prefix="/api/optimize", tags=["optimize"])

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


# ─── Analysis SPA (built by frontend/ Vite project) ───────────────────────────
# Route /job/{job_id}/analysis → serve the React SPA index.html.
# Assets (JS/CSS) are resolved via the already-mounted /static StaticFiles above
# once `npm run build` outputs to app/static/analysis/.

_ANALYSIS_SPA = STATIC_ROOT / "analysis" / "index.html"


@app.get("/job/{job_id}/analysis", response_model=None)
def analysis_page(job_id: int):
    """Serve the React analysis SPA for a given job."""
    if not _ANALYSIS_SPA.is_file():
        return {
            "detail": (
                "Analysis SPA not built yet. "
                "Run: cd frontend && npm install && npm run build"
            )
        }
    return FileResponse(_ANALYSIS_SPA)
