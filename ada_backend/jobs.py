from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ada_core import crear_zip_en_disco, descargar_item

from .config import Settings
from .models import CreateJobRequest, JobResponse, JobStatus, TrackResult
from .storage import LocalJobStorage


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobManager:
    """Ejecutor local reemplazable, con SQLite como registro de estado."""

    def __init__(self, config: Settings, storage: LocalJobStorage | None = None):
        self.config = config
        self.storage = storage or LocalJobStorage(config.data_dir / "files")
        config.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=config.max_workers, thread_name_prefix="ada-job")
        self._cancelled: set[str] = set()
        self._init_db()
        self._recover_interrupted()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.config.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _init_db(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, progress INTEGER NOT NULL,
                request_json TEXT NOT NULL, results_json TEXT NOT NULL, errors_json TEXT NOT NULL,
                created_at TEXT NOT NULL, expires_at TEXT NOT NULL, zip_path TEXT
            )""")

    def _recover_interrupted(self):
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, errors_json=? WHERE status IN (?, ?)",
                (JobStatus.failed, json.dumps(["El proceso del servidor se reinició"]), JobStatus.pending, JobStatus.running),
            )

    def submit(self, request: CreateJobRequest) -> JobResponse:
        self.cleanup_expired()
        if len(request.tracks) > self.config.max_tracks:
            raise ValueError(f"máximo {self.config.max_tracks} canciones por trabajo")
        job_id = str(uuid.uuid4())
        created = _now()
        expires = created + timedelta(seconds=self.config.job_ttl_seconds)
        self.storage.create(job_id)
        with self._connect() as db:
            db.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, JobStatus.pending, 0, request.model_dump_json(), "[]", "[]",
                 created.isoformat(), expires.isoformat(), None),
            )
        self._pool.submit(self._run, job_id, request)
        return self.get(job_id)

    def _run(self, job_id: str, request: CreateJobRequest):
        self._update(job_id, status=JobStatus.running)
        deadline = time.monotonic() + self.config.download_timeout_seconds
        results: list[dict] = []
        wav_files: list[str] = []
        try:
            total = len(request.tracks)
            for index, track in enumerate(request.tracks):
                if time.monotonic() >= deadline:
                    raise TimeoutError("el trabajo superó el tiempo máximo configurado")
                if job_id in self._cancelled:
                    self._update(job_id, status=JobStatus.cancelled, results=results)
                    return
                result = descargar_item(track.to_core(), request.quality, str(self.storage.path(job_id)))
                if result.get("ruta") and Path(result["ruta"]).is_file():
                    wav_files.append(result["ruta"])
                results.append(TrackResult(
                    track_id=track.id, status=result["estado"], message=result["mensaje"].replace("**", ""),
                    filename=Path(result["ruta"]).name if result.get("ruta") else None,
                ).model_dump())
                if job_id in self._cancelled:
                    self._update(job_id, status=JobStatus.cancelled, results=results)
                    return
                if self.storage.size(job_id) > self.config.max_job_bytes:
                    raise RuntimeError("el trabajo superó el límite de espacio configurado")
                self._update(job_id, progress=int((index + 1) * 90 / total), results=results)
            if job_id in self._cancelled:
                self._update(job_id, status=JobStatus.cancelled, results=results)
                return
            if not wav_files:
                raise RuntimeError("no se generaron archivos WAV")
            zip_path = self.storage.path(job_id) / "ada-download.zip"
            crear_zip_en_disco(wav_files, str(zip_path))
            self._update(job_id, status=JobStatus.completed, progress=100, results=results, zip_path=str(zip_path))
        except Exception as exc:
            self._update(job_id, status=JobStatus.failed, results=results, errors=[str(exc)])

    def _update(self, job_id: str, **values):
        columns, params = [], []
        for key, value in values.items():
            if key in {"results", "errors"}:
                key, value = f"{key}_json", json.dumps(value, ensure_ascii=False)
            if key == "status":
                value = value.value
            columns.append(f"{key}=?")
            params.append(value)
        with self._lock, self._connect() as db:
            db.execute(f"UPDATE jobs SET {', '.join(columns)} WHERE id=?", (*params, job_id))

    def get(self, job_id: str) -> JobResponse:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        expires = datetime.fromisoformat(row["expires_at"])
        status = JobStatus(row["status"])
        if expires <= _now() and status not in {JobStatus.expired, JobStatus.cancelled}:
            self.storage.delete(job_id)
            self._update(job_id, status=JobStatus.expired, zip_path=None)
            status = JobStatus.expired
        return JobResponse(
            id=job_id, status=status, progress=row["progress"],
            results=json.loads(row["results_json"]), errors=json.loads(row["errors_json"]),
            created_at=datetime.fromisoformat(row["created_at"]), expires_at=expires,
            download_url=f"/api/v1/jobs/{job_id}/download" if status is JobStatus.completed else None,
        )

    def cancel(self, job_id: str) -> JobResponse:
        job = self.get(job_id)
        if job.status in {JobStatus.completed, JobStatus.failed, JobStatus.expired}:
            raise ValueError("el trabajo ya terminó")
        self._cancelled.add(job_id)
        self._update(job_id, status=JobStatus.cancelled)
        return self.get(job_id)

    def zip_path(self, job_id: str) -> Path:
        job = self.get(job_id)
        if job.status is not JobStatus.completed:
            raise ValueError("el ZIP aún no está disponible")
        with self._connect() as db:
            row = db.execute("SELECT zip_path FROM jobs WHERE id=?", (job_id,)).fetchone()
        path = Path(row["zip_path"])
        if not path.is_file() or self.storage.path(job_id) not in path.resolve().parents:
            raise FileNotFoundError(path)
        return path

    def cleanup_expired(self) -> int:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM jobs WHERE expires_at <= ?", (_now().isoformat(),)).fetchall()
        for row in rows:
            self.storage.delete(row["id"])
            self._update(row["id"], status=JobStatus.expired, zip_path=None)
        return len(rows)

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)
