"""Stable event contract between an unknown XiaoHong wire protocol and services."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["device_to_cloud", "cloud_to_device"]


@dataclass(frozen=True)
class DeviceEnvelope:
    """A decoded transport frame after the listener removes transport details."""

    direction: Direction
    kind: Literal["text", "binary", "unknown"]
    payload: dict[str, Any] = field(default_factory=dict)
    audio: dict[str, Any] = field(default_factory=dict)
    raw_size: int = 0


@dataclass(frozen=True)
class CanonicalEvent:
    """Protocol-neutral event forwarded to the XiaoZhi/Hub integration boundary."""

    name: str
    device_id: str | None
    data: dict[str, Any]
    source: str = "xiaohong"


@dataclass(frozen=True)
class TranslationResult:
    """Translation result retaining all non-forwardable diagnostics locally."""

    event: CanonicalEvent | None
    accepted: bool
    reason: str | None = None
