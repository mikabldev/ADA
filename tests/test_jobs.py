import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ada_backend.config import Settings
from ada_backend.jobs import JobManager
from ada_backend.models import CreateJobRequest, JobStatus, Track


class JobTests(unittest.TestCase):
    def test_job_completes_and_builds_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Settings(root, root / "jobs.sqlite3", 5, 1, 1_000_000, 60, 10)
            manager = JobManager(config)

            def fake_download(item, quality, output_dir):
                path = Path(output_dir) / f"{item['nombre_salida']}.wav"
                path.write_bytes(b"wav")
                return {"estado": "descargada", "mensaje": "ok", "ruta": str(path)}

            request = CreateJobRequest(
                tracks=[Track(id="one", query="Artist - Track", output_name="Artist - Track")],
                quality="WAV 16-bit / 44.1 kHz",
            )
            with patch("ada_backend.jobs.descargar_item", side_effect=fake_download):
                submitted = manager.submit(request)
                self.assertIn(submitted.status, {JobStatus.pending, JobStatus.running})
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    job = manager.get(submitted.id)
                    if job.status not in {JobStatus.pending, JobStatus.running}:
                        break
                    time.sleep(0.01)

            self.assertEqual(job.status, JobStatus.completed)
            self.assertEqual(job.progress, 100)
            self.assertTrue(manager.zip_path(job.id).is_file())
            manager.shutdown()


if __name__ == "__main__":
    unittest.main()
