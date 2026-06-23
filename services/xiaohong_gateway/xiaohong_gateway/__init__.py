"""XiaoHong gateway core.

The package is transport-agnostic on purpose: WebSocket/MQTT listeners are
added only after the device capture defines the real wire protocol.
"""

from .contracts import CanonicalEvent, DeviceEnvelope, TranslationResult
from .session import GatewaySession, SessionState
from .translator import ProtocolProfile, XiaoHongTranslator

__all__ = [
    "CanonicalEvent",
    "DeviceEnvelope",
    "GatewaySession",
    "ProtocolProfile",
    "SessionState",
    "TranslationResult",
    "XiaoHongTranslator",
]
