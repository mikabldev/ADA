import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from mutagen.wave import WAVE

from ada_audio import analyze_audio, compare_audio
from ada_core import etiquetar_wav


def create_test_wave(path: Path, duration=6.0, sample_rate=22050):
    frames = []
    for index in range(int(duration * sample_rate)):
        time = index / sample_rate
        audible = 0.4 <= time <= duration - 0.4
        value = int(10000 * math.sin(2 * math.pi * 440 * time)) if audible else 0
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(frames))


class AudioAnalysisTests(unittest.TestCase):
    def test_extracts_features_and_embeds_dj_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.wav"
            create_test_wave(path)
            features = analyze_audio(path)
            self.assertAlmostEqual(features.duration_seconds, 6.0, places=1)
            self.assertGreater(features.audible_start_seconds, 0.2)
            self.assertLess(features.audible_end_seconds, 5.9)
            self.assertIsNotNone(features.fingerprint)

            item = {
                "nombre_salida": "Artist - Tone", "artista": "Artist", "titulo": "Tone",
                "album": "ADA Tests", "genero": "Electronic",
                "analisis_acustico": features.to_dict(),
            }
            self.assertTrue(etiquetar_wav(str(path), item))
            tags = WAVE(path).tags
            self.assertEqual(str(tags.get("TBPM")), f"{features.bpm:.2f}" if features.bpm else "None")
            self.assertEqual(str(tags.get("TCON")), "Electronic")
            self.assertIn("TXXX:ADA_CHROMAPRINT", tags)
            if features.camelot:
                self.assertEqual(str(tags.get("TKEY")), features.camelot)

    def test_identical_features_compare_as_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.wav"
            create_test_wave(path)
            features = analyze_audio(path)
            comparison = compare_audio(features, features)
            self.assertEqual(comparison["duration_delta_seconds"], 0)
            self.assertTrue(comparison["same_fingerprint"])
            self.assertAlmostEqual(comparison["intro_similarity"], 1, places=3)


if __name__ == "__main__":
    unittest.main()
