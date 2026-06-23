"""Profile-driven translation of XiaoHong wire messages into canonical events.

The default profile is intentionally narrow. Unknown messages are rejected and
recorded as diagnostics instead of being guessed or forwarded to XiaoZhi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import CanonicalEvent, DeviceEnvelope, TranslationResult


@dataclass(frozen=True)
class ProtocolProfile:
    """Observed wire-event names for one XiaoHong firmware family/version."""

    name: str = "xiaohong-observed-v0"
    board: str = "xiaohong_v1"
    registration_events: frozenset[str] = frozenset({"hello", "register", "device_register"})
    audio_up_events: frozenset[str] = frozenset({"audio_in", "audio_up", "listen"})
    audio_down_events: frozenset[str] = frozenset({"audio_out", "audio_down", "speak"})
    interruption_events: frozenset[str] = frozenset({"abort", "interrupt", "stop"})
    capability_events: frozenset[str] = frozenset({"capability", "capabilities", "device_status"})
    acknowledgement_events: frozenset[str] = frozenset({"ack", "acknowledge"})
    aliases: dict[str, str] = field(default_factory=dict)

    def canonical_wire_name(self, value: str) -> str:
        value = value.strip().lower()
        return self.aliases.get(value, value)


class XiaoHongTranslator:
    """Translate only confirmed message shapes; never invent a device identity."""

    def __init__(self, profile: ProtocolProfile | None = None) -> None:
        self.profile = profile or ProtocolProfile()

    @staticmethod
    def _event_name(payload: dict[str, Any]) -> str:
        for key in ("type", "event", "action", "cmd", "command"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    @staticmethod
    def _device_id(payload: dict[str, Any]) -> str | None:
        for key in ("device_id", "deviceId", "mac", "macAddress", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _safe_audio_metadata(audio: dict[str, Any]) -> dict[str, Any]:
        allowed = {"codec", "sample_rate", "channels", "frame_ms", "sequence", "duration_ms"}
        return {key: value for key, value in audio.items() if key in allowed}

    def translate(self, envelope: DeviceEnvelope) -> TranslationResult:
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        wire_event = self.profile.canonical_wire_name(self._event_name(payload))
        device_id = self._device_id(payload)

        if wire_event in self.profile.registration_events:
            board = str(payload.get("board") or self.profile.board)
            if board != self.profile.board:
                return TranslationResult(None, False, f"unexpected board: {board}")
            if not device_id:
                return TranslationResult(None, False, "registration missing device identity")
            return TranslationResult(
                CanonicalEvent(
                    "device.registered",
                    device_id,
                    {
                        "board": board,
                        "app_version": payload.get("appVersion") or payload.get("app_version"),
                        "firmware_version": payload.get("firmwareVersion") or payload.get("firmware_version"),
                    },
                ),
                True,
            )

        if envelope.kind == "binary" and envelope.direction == "device_to_cloud":
            if not device_id:
                return TranslationResult(None, False, "audio frame missing device identity")
            return TranslationResult(
                CanonicalEvent(
                    "audio.upstream",
                    device_id,
                    {"event": wire_event or "binary", "audio": self._safe_audio_metadata(envelope.audio), "bytes": envelope.raw_size},
                ),
                True,
            )

        if envelope.kind == "binary" and envelope.direction == "cloud_to_device":
            if not device_id:
                return TranslationResult(None, False, "downstream audio missing device identity")
            return TranslationResult(
                CanonicalEvent(
                    "audio.downstream",
                    device_id,
                    {"event": wire_event or "binary", "audio": self._safe_audio_metadata(envelope.audio), "bytes": envelope.raw_size},
                ),
                True,
            )

        if wire_event in self.profile.interruption_events:
            return TranslationResult(CanonicalEvent("conversation.interrupted", device_id, {"event": wire_event}), True)
        if wire_event in self.profile.capability_events:
            capabilities = payload.get("capabilities")
            if not isinstance(capabilities, (dict, list)):
                capabilities = payload.get("data", {})
            return TranslationResult(CanonicalEvent("device.capabilities", device_id, {"capabilities": capabilities}), True)
        if wire_event in self.profile.acknowledgement_events:
            return TranslationResult(CanonicalEvent("device.acknowledged", device_id, {"ack": payload.get("ack") or payload.get("requestId")}), True)

        return TranslationResult(None, False, f"unmapped wire event: {wire_event or envelope.kind}")
