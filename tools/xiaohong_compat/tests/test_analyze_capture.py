import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analyze_capture", ROOT / "analyze_capture.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AnalyzeCaptureTest(unittest.TestCase):
    def test_ws_opus_is_adapter_candidate(self):
        records = MODULE.load_capture(ROOT / "tests" / "fixtures" / "xiaohong_ws_opus.jsonl")
        report = MODULE.analyze_records(records)
        self.assertEqual(report["assessment"]["verdict"], "adapter_candidate")
        self.assertIn("wss", report["observed"]["transports"])
        self.assertIn("opus", report["observed"]["audio_codecs"])

    def test_empty_capture_is_insufficient(self):
        report = MODULE.analyze_records([])
        self.assertEqual(report["assessment"]["verdict"], "insufficient_evidence")

    def test_unknown_transport_prefers_separation(self):
        report = MODULE.analyze_records([
            {"transport": "quic", "endpoint": "quic://cloud.example", "kind": "binary"}
        ])
        self.assertEqual(report["assessment"]["verdict"], "separate_cloud_or_protocol_gateway")


if __name__ == "__main__":
    unittest.main()
