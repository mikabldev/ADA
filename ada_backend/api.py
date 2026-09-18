from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .jobs import JobManager
from .models import AnalyzeRequest, AnalyzeResponse, CreateJobRequest, JobResponse
from .service import analyze_url

manager = JobManager(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager.cleanup_expired()
    async def cleanup_loop():
        while True:
            await asyncio.sleep(60)
            manager.cleanup_expired()
    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    cleanup_task.cancel()
    manager.shutdown()


app = FastAPI(title="ADA API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    try:
        tracks = analyze_url(request.platform, str(request.url), settings.max_tracks)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, detail=f"no se pudo analizar la URL: {exc}") from exc
    if not tracks:
        raise HTTPException(404, detail="no se detectaron canciones")
    return AnalyzeResponse(tracks=tracks)


@app.post("/api/v1/jobs", response_model=JobResponse, status_code=202)
def create_job(request: CreateJobRequest):
    try:
        return manager.submit(request)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    try:
        return manager.get(job_id)
    except (KeyError, ValueError):
        raise HTTPException(404, detail="trabajo no encontrado")


@app.delete("/api/v1/jobs/{job_id}", response_model=JobResponse)
def cancel_job(job_id: str):
    try:
        return manager.cancel(job_id)
    except KeyError:
        raise HTTPException(404, detail="trabajo no encontrado")
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@app.get("/api/v1/jobs/{job_id}/download")
def download_job(job_id: str):
    try:
        path = manager.zip_path(job_id)
    except KeyError:
        raise HTTPException(404, detail="trabajo no encontrado")
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(410, detail="el archivo expiró o fue eliminado")
    return FileResponse(path, media_type="application/zip", filename="ada-download.zip")
