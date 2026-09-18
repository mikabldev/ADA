from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import librosa
import numpy as np


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
CAMELOT = {
    ("G#", "minor"): "1A", ("B", "major"): "1B",
    ("D#", "minor"): "2A", ("F#", "major"): "2B",
    ("A#", "minor"): "3A", ("C#", "major"): "3B",
    ("F", "minor"): "4A", ("G#", "major"): "4B",
    ("C", "minor"): "5A", ("D#", "major"): "5B",
    ("G", "minor"): "6A", ("A#", "major"): "6B",
    ("D", "minor"): "7A", ("F", "major"): "7B",
    ("A", "minor"): "8A", ("C", "major"): "8B",
    ("E", "minor"): "9A", ("G", "major"): "9B",
    ("B", "minor"): "10A", ("D", "major"): "10B",
    ("F#", "minor"): "11A", ("A", "major"): "11B",
    ("C#", "minor"): "12A", ("E", "major"): "12B",
}


@dataclass(frozen=True)
class AudioFeatures:
    duration_seconds: float
    bpm: float | None
    bpm_confidence: float | None
    musical_key: str | None
    scale: str | None
    camelot: str | None
    key_confidence: float | None
    audible_start_seconds: float
    audible_end_seconds: float
    intro_chroma: list[float]
    outro_chroma: list[float]
    fingerprint: str | None
    analyzer_version: str = "ada-audio-v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _estimate_key(chroma: np.ndarray) -> tuple[str | None, str | None, float | None]:
    if chroma.size == 0:
        return None, None, None
    observed = np.mean(chroma, axis=1)
    if not np.any(observed):
        return None, None, None
    scores = []
    for tonic, name in enumerate(NOTE_NAMES):
        scores.append((float(np.corrcoef(observed, np.roll(MAJOR_PROFILE, tonic))[0, 1]), name, "major"))
        scores.append((float(np.corrcoef(observed, np.roll(MINOR_PROFILE, tonic))[0, 1]), name, "minor"))
    score, key, scale = max(scores, key=lambda value: value[0])
    return key, scale, round(max(0.0, min(1.0, (score + 1) / 2)), 3)


def _section_mean(chroma: np.ndarray, seconds: float, sample_rate: int, from_end=False) -> list[float]:
    frames = max(1, librosa.time_to_frames(seconds, sr=sample_rate))
    section = chroma[:, -frames:] if from_end else chroma[:, :frames]
    values = np.mean(section, axis=1) if section.size else np.zeros(12)
    norm = np.linalg.norm(values)
    if norm:
        values = values / norm
    return [round(float(value), 6) for value in values]


def _chromaprint(path: Path) -> str | None:
    try:
        process = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "chromaprint", "-fp_format", "base64", "-"],
            capture_output=True, check=True, timeout=120,
        )
        value = process.stdout.strip()
        if not value:
            return None
        return value.decode("ascii", errors="ignore")
    except (OSError, subprocess.SubprocessError):
        return None


def analyze_audio(path: str | Path) -> AudioFeatures:
    """Extrae descriptores reproducibles sin llamadas a servicios externos."""
    audio_path = Path(path).resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)
    sample_rate = 22050
    signal, sample_rate = librosa.load(audio_path, sr=sample_rate, mono=True)
    if signal.size == 0:
        raise ValueError("el archivo de audio está vacío")
    duration = float(librosa.get_duration(y=signal, sr=sample_rate))
    _, audible = librosa.effects.trim(signal, top_db=45)
    onset = librosa.onset.onset_strength(y=signal, sr=sample_rate)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sample_rate)
    bpm = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else None
    beat_count = int(np.asarray(beats).size)
    bpm_confidence = min(1.0, beat_count / max(8.0, duration / 2)) if bpm else None
    chroma = librosa.feature.chroma_cqt(y=signal, sr=sample_rate)
    key, scale, key_confidence = _estimate_key(chroma)
    return AudioFeatures(
        duration_seconds=round(duration, 3), bpm=round(bpm, 2) if bpm else None,
        bpm_confidence=round(bpm_confidence, 3) if bpm_confidence is not None else None,
        musical_key=key, scale=scale,
        camelot=CAMELOT.get((key, scale)) if key and scale else None,
        key_confidence=key_confidence,
        audible_start_seconds=round(float(audible[0]) / sample_rate, 3),
        audible_end_seconds=round(float(audible[1]) / sample_rate, 3),
        intro_chroma=_section_mean(chroma, 30, sample_rate),
        outro_chroma=_section_mean(chroma, 30, sample_rate, from_end=True),
        fingerprint=_chromaprint(audio_path),
    )


def _cosine(left: list[float], right: list[float]) -> float:
    a, b = np.asarray(left), np.asarray(right)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def compare_audio(reference: AudioFeatures, candidate: AudioFeatures) -> dict:
    """Compara atributos; no declara identidad sin una huella o referencia suficiente."""
    bpm_delta = None
    if reference.bpm and candidate.bpm:
        ratios = (candidate.bpm, candidate.bpm / 2, candidate.bpm * 2)
        bpm_delta = min(abs(reference.bpm - value) for value in ratios)
    return {
        "duration_delta_seconds": round(abs(reference.duration_seconds - candidate.duration_seconds), 3),
        "bpm_delta": round(bpm_delta, 3) if bpm_delta is not None else None,
        "same_key": bool(reference.camelot and reference.camelot == candidate.camelot),
        "intro_similarity": round(_cosine(reference.intro_chroma, candidate.intro_chroma), 4),
        "outro_similarity": round(_cosine(reference.outro_chroma, candidate.outro_chroma), 4),
        "same_fingerprint": bool(reference.fingerprint and reference.fingerprint == candidate.fingerprint),
    }
