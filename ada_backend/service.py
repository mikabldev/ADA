from __future__ import annotations

import hashlib

from ada_core import obtener_metadatos_cancion_unica, obtener_metadatos_spotify, obtener_metadatos_ytdlp

from .models import Platform, Track


def analyze_url(platform: Platform, url: str, max_tracks: int) -> list[Track]:
    if platform is Platform.spotify:
        raw = obtener_metadatos_spotify(url)
    elif platform in {Platform.youtube, Platform.soundcloud}:
        raw = obtener_metadatos_ytdlp(url, platform.value.title())
    else:
        raw = obtener_metadatos_cancion_unica(url)
    if len(raw) > max_tracks:
        raise ValueError(f"la URL contiene más de {max_tracks} canciones")
    return [_track(item, index) for index, item in enumerate(raw)]


def _track(item: dict, index: int) -> Track:
    query = str(item.get("query_limpia") or item.get("nombre_salida") or "").strip()
    digest = hashlib.sha256(f"{index}:{query}".encode()).hexdigest()[:16]
    return Track(
        id=digest, query=query, output_name=str(item.get("nombre_salida") or query)[:180],
        artist=item.get("artista"), title=item.get("titulo"), album=item.get("album"),
        duration_ms=item.get("duration_ms"), direct_url=item.get("url_directa"),
    )
