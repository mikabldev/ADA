from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from ada_core import CALIDADES_AUDIO, limpiar_nombre_archivo


class Platform(str, Enum):
    spotify = "spotify"
    youtube = "youtube"
    soundcloud = "soundcloud"
    bandcamp = "bandcamp"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"


class Track(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=500)
    output_name: str = Field(min_length=1, max_length=180)
    artist: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=300)
    album: str | None = Field(default=None, max_length=300)
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    direct_url: HttpUrl | None = None

    @field_validator("output_name")
    @classmethod
    def safe_output_name(cls, value: str) -> str:
        cleaned = limpiar_nombre_archivo(value).strip(". ")
        if not cleaned or cleaned != value or value in {".", ".."}:
            raise ValueError("nombre de archivo no válido")
        return cleaned

    def to_core(self) -> dict:
        return {
            "query_limpia": self.query, "nombre_salida": self.output_name,
            "artista": self.artist, "titulo": self.title, "album": self.album,
            "duration_ms": self.duration_ms,
            "url_directa": str(self.direct_url) if self.direct_url else None,
        }


class AnalyzeRequest(BaseModel):
    platform: Platform
    url: HttpUrl

    @model_validator(mode="after")
    def matching_host(self):
        host = (self.url.host or "").lower()
        if self.url.username or self.url.password or self.url.port not in {None, 80, 443}:
            raise ValueError("la URL no puede incluir credenciales ni puertos personalizados")
        allowed = {
            Platform.spotify: ("spotify.com",), Platform.youtube: ("youtube.com", "youtu.be"),
            Platform.soundcloud: ("soundcloud.com",), Platform.bandcamp: ("bandcamp.com",),
        }[self.platform]
        if not any(host == domain or host.endswith(f".{domain}") for domain in allowed):
            raise ValueError("la URL no corresponde a la plataforma seleccionada")
        return self


class AnalyzeResponse(BaseModel):
    tracks: list[Track]


class CreateJobRequest(BaseModel):
    tracks: Annotated[list[Track], Field(min_length=1)]
    quality: str

    @field_validator("quality")
    @classmethod
    def supported_quality(cls, value: str) -> str:
        if value not in CALIDADES_AUDIO:
            raise ValueError(f"calidad no válida; opciones: {', '.join(CALIDADES_AUDIO)}")
        return value

    @model_validator(mode="after")
    def unique_outputs(self):
        names = [track.output_name.casefold() for track in self.tracks]
        if len(names) != len(set(names)):
            raise ValueError("los nombres de salida deben ser únicos dentro del trabajo")
        return self


class TrackResult(BaseModel):
    track_id: str
    status: str
    message: str
    filename: str | None = None


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    progress: Annotated[int, Field(ge=0, le=100)]
    results: list[TrackResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime
    download_url: str | None = None
