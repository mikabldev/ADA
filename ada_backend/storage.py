from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol


class JobStorage(Protocol):
    def create(self, job_id: str) -> Path: ...
    def delete(self, job_id: str) -> None: ...
    def size(self, job_id: str) -> int: ...


class LocalJobStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, job_id: str) -> Path:
        if not job_id or any(c not in "0123456789abcdef-" for c in job_id.lower()):
            raise ValueError("identificador de job no válido")
        result = (self.root / job_id).resolve()
        if self.root not in result.parents:
            raise ValueError("ruta de job fuera del almacenamiento")
        return result

    def create(self, job_id: str) -> Path:
        path = self.path(job_id)
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
        return path

    def delete(self, job_id: str) -> None:
        path = self.path(job_id)
        if path.exists():
            shutil.rmtree(path)

    def size(self, job_id: str) -> int:
        path = self.path(job_id)
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0
