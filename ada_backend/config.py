from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    value = int(os.getenv(name, default))
    if value < 1:
        raise ValueError(f"{name} debe ser mayor que cero")
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    max_tracks: int
    max_workers: int
    max_job_bytes: int
    job_ttl_seconds: int
    download_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("ADA_DATA_DIR", Path(tempfile.gettempdir()) / "ada-jobs")).resolve()
        database_path = Path(os.getenv("ADA_DATABASE_PATH", data_dir / "jobs.sqlite3")).resolve()
        return cls(
            data_dir=data_dir,
            database_path=database_path,
            max_tracks=_int_env("ADA_MAX_TRACKS", 100),
            max_workers=_int_env("ADA_MAX_WORKERS", 2),
            max_job_bytes=_int_env("ADA_MAX_JOB_BYTES", 5 * 1024**3),
            job_ttl_seconds=_int_env("ADA_JOB_TTL_SECONDS", 3600),
            download_timeout_seconds=_int_env("ADA_DOWNLOAD_TIMEOUT_SECONDS", 1800),
        )


settings = Settings.from_env()
