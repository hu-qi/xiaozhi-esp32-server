import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("probe_console_api", ROOT / "probe_console_api.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ProbeConsoleApiTest(unittest.TestCase):
    def test_authenticated_probe_redacts_data(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.full_url, request.get_header("Authorization")))
            return FakeResponse(
                200,
                {
                    "code": 0,
                    "msg": "success",
                    "data": {"token": "secret", "board": "xiaohong_v1"},
                },
            )

        report = MODULE.run_probes(
            "https://example.test/xiaohong",
            "top-secret",
            agent_id="agent-1",
            opener=opener,
        )

        self.assertEqual(report["passed"], 6)
        self.assertEqual(len(seen), 6)
        self.assertIsNone(seen[0][1])
        self.assertTrue(all(auth == "Bearer top-secret" for _, auth in seen[1:]))
        self.assertEqual(report["results"][1]["data"]["board"], "xiaohong_v1")
        self.assertNotIn("token", report["results"][1]["data"]["keys"])

    def test_missing_token_skips_private_endpoints(self):
        report = MODULE.run_probes(
            "http://example.test/xiaohong",
            None,
            opener=lambda *args, **kwargs: FakeResponse(200, {"code": 0, "data": {}}),
        )
        self.assertTrue(report["results"][1]["skipped"])
        self.assertEqual(report["results"][1]["reason"], "missing AURAAUDIO_TOKEN")

    def test_invalid_base_url_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.run_probes("console.example", "token")


if __name__ == "__main__":
    unittest.main()
