import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xiaohong_gateway.contracts import DeviceEnvelope
from xiaohong_gateway.replay import replay
from xiaohong_gateway.session import GatewaySession, SessionState
from xiaohong_gateway.translator import XiaoHongTranslator


class GatewaySessionTest(unittest.TestCase):
    def setUp(self):
        self.session = GatewaySession(XiaoHongTranslator())

    def test_audio_requires_registration(self):
        result = self.session.process(
            DeviceEnvelope("device_to_cloud", "binary", audio={"codec": "opus"}, raw_size=100)
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "audio frame missing device identity")

    def test_registration_hydrates_following_audio_frame(self):
        registered = self.session.process(
            DeviceEnvelope(
                "device_to_cloud",
                "text",
                payload={"type": "hello", "device_id": "AA:BB", "board": "xiaohong_v1"},
            )
        )
        audio = self.session.process(
            DeviceEnvelope("device_to_cloud", "binary", audio={"codec": "opus", "sample_rate": 16000}, raw_size=480)
        )
        self.assertTrue(registered.accepted)
        self.assertEqual(self.session.state, SessionState.REGISTERED)
        self.assertTrue(audio.accepted)
        self.assertEqual(audio.event.name, "audio.upstream")
        self.assertEqual(audio.event.device_id, "AA:BB")

    def test_identity_cannot_change(self):
        self.session.process(
            DeviceEnvelope("device_to_cloud", "text", payload={"type": "hello", "device_id": "AA", "board": "xiaohong_v1"})
        )
        result = self.session.process(
            DeviceEnvelope("device_to_cloud", "text", payload={"type": "interrupt", "device_id": "CC"})
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "device identity changed within one session")

    def test_replay_rejects_unknown_event_without_crashing(self):
        result = replay(
            [
                {"direction": "device_to_cloud", "kind": "text", "payload": {"type": "hello", "device_id": "AA", "board": "xiaohong_v1"}},
                {"direction": "device_to_cloud", "kind": "text", "payload": {"type": "future_event"}},
            ]
        )
        self.assertTrue(result[0]["accepted"])
        self.assertFalse(result[1]["accepted"])
        self.assertIn("unmapped wire event", result[1]["reason"])


if __name__ == "__main__":
    unittest.main()
