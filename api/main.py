"""FastAPI backend for the Multi-Agent Research Assistant.

Endpoints:
  GET  /health            — liveness check
  POST /research          — submit a new research job
  GET  /status/{job_id}  — poll job status
  GET  /result/{job_id}  — fetch completed result
  GET  /stream/{job_id}  — SSE stream of agent log events
  GET  /download/{job_id}— download the generated PDF

The in-memory job store (_jobs dict) is intentional for local / single-
instance deployments. For production scale-out, replace with Redis and
Celery (or a similar distributed task queue).
"""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from agents.orchestrator import run_research

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Research Assistant API",
    version="1.0.0",
    description="Multi-agent research system powered by GPT-4o, LangGraph, MCP, and Guardrails AI.",
)

# Allow Streamlit frontend (and local dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ──────────────────────────────────────────────────────
# Structure: { job_id: { status, logs, result, error } }
_jobs: dict[str, dict[str, Any]] = {}


# ── Request / Response models ────────────────────────────────────────────────


class ResearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The research question to investigate.",
        example="What are the latest trends in Generative AI for 2025?",
    )


class JobResponse(BaseModel):
    job_id: str
    status: str


# ── Routes ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["Operations"])
async def health() -> dict:
    """Liveness check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/research", response_model=JobResponse, tags=["Research"], status_code=202)
async def start_research(req: ResearchRequest, bg: BackgroundTasks) -> JobResponse:
    """Submit a new research job.

    The job runs asynchronously in a background task. Poll /status/{job_id}
    or stream /stream/{job_id} for progress.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "PENDING", "logs": [], "result": None, "error": None}
    bg.add_task(_run_job, job_id, req.query)
    logger.info(f"Queued job {job_id}")
    return JobResponse(job_id=job_id, status="PENDING")


async def _run_job(job_id: str, query: str) -> None:
    """Background task: execute the research pipeline and update job store."""
    _jobs[job_id]["status"] = "RUNNING"
    try:
        # run_research is synchronous (LangGraph); run in executor to avoid
        # blocking the event loop.
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, run_research, query, job_id
        )
        _jobs[job_id].update(
            {
                "status": "COMPLETE",
                "result": dict(result),
                "logs": result.get("logs", []),
            }
        )
        logger.info(f"Job {job_id} completed successfully")
    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}", exc_info=True)
        _jobs[job_id].update({"status": "FAILED", "error": str(exc)})


@app.get("/status/{job_id}", tags=["Research"])
async def get_status(job_id: str) -> dict:
    """Return the current status of a research job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, "status": job["status"]}


@app.get("/result/{job_id}", tags=["Research"])
async def get_result(job_id: str) -> dict:
    """Return the full result of a completed research job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job["status"] != "COMPLETE":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not complete yet (current status: {job['status']})",
        )
    return job["result"]


@app.get("/stream/{job_id}", tags=["Research"])
async def stream_logs(job_id: str) -> StreamingResponse:
    """Stream agent log events via Server-Sent Events (SSE).

    Each event is emitted as:
        data: <log message>

    The stream terminates with:
        data: STATUS:COMPLETE
      or
        data: STATUS:FAILED
    """

    async def event_generator():
        seen = 0
        while True:
            job = _jobs.get(job_id, {})
            logs: list[str] = job.get("logs", [])

            # Emit any new log lines
            for log in logs[seen:]:
                yield f"data: {log}\n\n"
                seen += 1

            status = job.get("status", "PENDING")
            if status in ("COMPLETE", "FAILED"):
                yield f"data: STATUS:{status}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/download/{job_id}", tags=["Research"])
async def download_pdf(job_id: str) -> FileResponse:
    """Download the PDF report generated for a completed job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job["status"] != "COMPLETE":
        raise HTTPException(
            status_code=400,
            detail=f"Result not ready (status: {job['status']})",
        )
    pdf_path: str = job["result"].get("pdf_path", "")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="No PDF was generated for this job")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="research_report.pdf",
    )
