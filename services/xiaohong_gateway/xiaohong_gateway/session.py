"""Connection-scoped state machine for the XiaoHong gateway."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .contracts import DeviceEnvelope, TranslationResult
from .translator import XiaoHongTranslator


class SessionState(str, Enum):
    CONNECTED = "connected"
    REGISTERED = "registered"
    CLOSED = "closed"


@dataclass
class GatewaySession:
    """Preserves device identity after registration and blocks invalid ordering."""

    translator: XiaoHongTranslator
    state: SessionState = SessionState.CONNECTED
    device_id: str | None = None

    def process(self, envelope: DeviceEnvelope) -> TranslationResult:
        if self.state is SessionState.CLOSED:
            return TranslationResult(None, False, "session is closed")

        hydrated = envelope
        if self.device_id and not self._has_device_id(envelope):
            payload = dict(envelope.payload)
            payload["device_id"] = self.device_id
            hydrated = replace(envelope, payload=payload)

        result = self.translator.translate(hydrated)
        if not result.accepted:
            return result

        if result.event and result.event.name == "device.registered":
            self.device_id = result.event.device_id
            self.state = SessionState.REGISTERED
            return result

        if self.state is not SessionState.REGISTERED:
            return TranslationResult(None, False, "device must register before sending non-registration events")
        if result.event and result.event.device_id and self.device_id != result.event.device_id:
            return TranslationResult(None, False, "device identity changed within one session")
        return result

    def close(self) -> None:
        self.state = SessionState.CLOSED

    @staticmethod
    def _has_device_id(envelope: DeviceEnvelope) -> bool:
        return any(
            isinstance(envelope.payload.get(key), str) and envelope.payload[key].strip()
            for key in ("device_id", "deviceId", "mac", "macAddress", "id")
        )
