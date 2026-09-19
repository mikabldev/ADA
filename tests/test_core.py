import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from ada_core import (
    buscar_candidatos_multifuente,
    clasificar_coincidencia,
    construir_ydl_opts,
    crear_zip_en_disco,
    descargar_item,
    limpiar_nombre_archivo,
    obtener_metadatos_spotify,
)


class CoreTests(unittest.TestCase):
    def test_download_directory_is_injected(self):
        with tempfile.TemporaryDirectory() as tmp:
            opts = construir_ydl_opts("track", "WAV 16-bit / 44.1 kHz", tmp)
            self.assertTrue(opts["outtmpl"].startswith(str(Path(tmp).resolve())))

    def test_zip_contains_only_base_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "track.wav"
            source.write_bytes(b"wav")
            archive = root / "result.zip"
            crear_zip_en_disco([str(source)], str(archive))
            self.assertTrue(archive.is_file())

    def test_filename_sanitizer(self):
        self.assertEqual(limpiar_nombre_archivo('a<>:"/\\|?*b'), "ab")

    def test_default_source_order_starts_with_bandcamp(self):
        seen = []

        def fake_search(query, source):
            seen.append(source)
            return []

        with patch("ada_core._buscar_candidatos_fuente", side_effect=fake_search):
            buscar_candidatos_multifuente("Artist - Track")
        self.assertEqual(seen, ["Bandcamp", "SoundCloud", "YouTube"])

    def test_spotify_oauth_extractor_supports_new_and_legacy_item_fields(self):
        class FakeSpotify:
            def playlist_items(self, playlist_id, **kwargs):
                self.playlist_id = playlist_id
                return {
                    "items": [{"item": {
                        "type": "track", "name": "Track One", "duration_ms": 180_000,
                        "artists": [{"name": "Artist A"}], "album": {"name": "Album A"},
                    }}],
                    "next": "page-2",
                }

            def next(self, page):
                return {
                    "items": [{"track": {
                        "type": "track", "name": "Track Two", "duration_ms": 200_000,
                        "artists": [{"name": "Artist B"}, {"name": "Artist C"}],
                        "album": {"name": "Album B"},
                    }}],
                    "next": None,
                }

        spotify = FakeSpotify()
        tracks = obtener_metadatos_spotify(
            "https://open.spotify.com/playlist/3p1gL9zMswgYVengeckEsx?si=test",
            spotify=spotify,
        )

        self.assertEqual(spotify.playlist_id, "3p1gL9zMswgYVengeckEsx")
        self.assertEqual([track["titulo"] for track in tracks], ["Track One", "Track Two"])
        self.assertEqual(tracks[1]["artista"], "Artist B, Artist C")

    def test_spotify_oauth_extractor_rejects_invalid_url(self):
        with self.assertRaisesRegex(ValueError, "identificador"):
            obtener_metadatos_spotify("https://example.com/not-a-playlist", spotify=object())

    def test_studio_variant_is_sent_to_review(self):
        item = {"query_limpia": "Artist - Track", "duration_ms": 180_000}
        candidates = [
            {"title": "Artist - Track (Studio Version)", "uploader": "Artist", "duration": 180,
             "webpage_url": "https://example.bandcamp.com/track/studio", "_ada_fuente": "Bandcamp"},
            {"title": "Artist - Track", "uploader": "Artist", "duration": 181,
             "webpage_url": "https://soundcloud.com/artist/track", "_ada_fuente": "SoundCloud"},
        ]
        result = clasificar_coincidencia(item, candidates)
        self.assertEqual(result["estado"], "revision")
        self.assertTrue(any("varias versiones" in reason for reason in result["motivos"]))

    def test_duration_difference_forces_review(self):
        item = {"query_limpia": "Artist - Track", "duration_ms": 180_000}
        candidates = [{
            "title": "Artist - Track", "uploader": "Artist", "duration": 230,
            "webpage_url": "https://youtube.com/watch?v=x", "_ada_fuente": "YouTube",
        }]
        result = clasificar_coincidencia(item, candidates, {"similitud_minima": 40})
        self.assertEqual(result["estado"], "revision")
        self.assertTrue(any("duración difiere" in reason for reason in result["motivos"]))

    def test_verified_candidate_never_falls_back_to_another_version(self):
        calls = []

        class FakeYDL:
            def __init__(self, options):
                self.options = options
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def download(self, urls):
                calls.extend(urls)
                raise RuntimeError("source unavailable")

        item = {
            "query_limpia": "Artist - Track", "nombre_salida": "Artist - Track",
            "url_directa": "https://artist.bandcamp.com/track/track",
            "fuente_seleccionada": "Bandcamp", "bloquear_fallback": True,
        }
        with tempfile.TemporaryDirectory() as tmp, patch("ada_core.yt_dlp.YoutubeDL", FakeYDL):
            result = descargar_item(item, "WAV 16-bit / 44.1 kHz", tmp)
        self.assertEqual(result["estado"], "fallida")
        self.assertEqual(calls, [item["url_directa"]])


if __name__ == "__main__":
    unittest.main()
