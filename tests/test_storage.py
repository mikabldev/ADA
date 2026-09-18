import tempfile
import unittest
from pathlib import Path

from ada_backend.storage import LocalJobStorage


class StorageTests(unittest.TestCase):
    def test_job_is_isolated_and_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalJobStorage(Path(tmp))
            job = "01234567-89ab-cdef-0123-456789abcdef"
            path = storage.create(job)
            (path / "track.wav").write_bytes(b"wav")
            self.assertEqual(storage.size(job), 3)
            storage.delete(job)
            self.assertFalse(path.exists())

    def test_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = LocalJobStorage(Path(tmp))
            with self.assertRaises(ValueError):
                storage.path("../outside")


if __name__ == "__main__":
    unittest.main()
