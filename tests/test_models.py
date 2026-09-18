import unittest

from pydantic import ValidationError

from ada_backend.models import AnalyzeRequest, CreateJobRequest, Platform, Track


class ModelTests(unittest.TestCase):
    def test_platform_must_match_host(self):
        with self.assertRaises(ValidationError):
            AnalyzeRequest(platform=Platform.spotify, url="https://youtube.com/watch?v=x")

    def test_custom_port_is_rejected(self):
        with self.assertRaises(ValidationError):
            AnalyzeRequest(platform=Platform.youtube, url="https://youtube.com:8443/watch?v=x")

    def test_unsafe_filename_is_rejected(self):
        with self.assertRaises(ValidationError):
            Track(id="one", query="a", output_name="../a")

    def test_duplicate_outputs_are_rejected(self):
        tracks = [Track(id=str(i), query=str(i), output_name="Same") for i in range(2)]
        with self.assertRaises(ValidationError):
            CreateJobRequest(tracks=tracks, quality="WAV 16-bit / 44.1 kHz")


if __name__ == "__main__":
    unittest.main()
