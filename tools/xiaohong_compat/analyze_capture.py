#!/usr/bin/env python3
"""Analyze a captured XiaoHong cloud session against XiaoZhi transport expectations.

The tool deliberately produces a conservative recommendation. It does not
claim protocol compatibility simply because both sides use WebSocket or Opus.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_TRANSPORTS = {"ws", "wss", "mqtt", "udp"}
XIAOZHI_HINTS = {
    "websocket_path": "/xiaozhi/v1/",
    "ota_path": "/xiaozhi/ota/",
    "audio_codec": "opus",
}


def _normalise_transport(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalise_codec(record: dict[str, Any]) -> str:
    audio = record.get("audio")
    if isinstance(audio, dict):
        return str(audio.get("codec") or "").strip().lower()
    return ""


def _event_name(record: dict[str, Any]) -> str:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return ""
    for key in ("type", "event", "action", "cmd", "command"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def load_capture(path: Path) -> list[dict[str, Any]]:
    """Load either a JSON array or JSON Lines capture file."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                decoded.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
    if not isinstance(decoded, list):
        raise ValueError("Capture must be a JSON array or JSON Lines file.")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(decoded, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Capture record {index} must be a JSON object.")
        records.append(record)
    return records


def _dedupe(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})


def analyze_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    transports = _dedupe(_normalise_transport(record.get("transport")) for record in records)
    endpoints = _dedupe(str(record.get("endpoint") or "").strip() for record in records)
    codecs = _dedupe(_normalise_codec(record) for record in records)
    events = _dedupe(_event_name(record) for record in records)
    kinds = Counter(str(record.get("kind") or "unknown").strip().lower() for record in records)

    unsupported_transports = sorted(set(transports) - SUPPORTED_TRANSPORTS)
    supports_known_transport = bool(set(transports) & SUPPORTED_TRANSPORTS)
    has_opus = "opus" in codecs
    has_audio_evidence = bool(codecs)
    has_ws = bool({"ws", "wss"} & set(transports))
    has_mqtt_udp = {"mqtt", "udp"}.issubset(set(transports))
    xiaozhi_path_seen = any(XIAOZHI_HINTS["websocket_path"] in endpoint for endpoint in endpoints)
    ota_path_seen = any(XIAOZHI_HINTS["ota_path"] in endpoint for endpoint in endpoints)

    risks: list[str] = []
    next_checks: list[str] = []
    if not records:
        verdict = "insufficient_evidence"
        recommendation = "Capture a complete wake-up → request → TTS playback session before selecting a server strategy."
        confidence = "none"
    elif unsupported_transports and not supports_known_transport:
        verdict = "separate_cloud_or_protocol_gateway"
        recommendation = "Keep XiaoHong cloud/client work separate. Build a protocol gateway only after documenting the proprietary transport and authentication flow."
        confidence = "medium"
        risks.append("No XiaoZhi-supported transport was observed.")
    elif supports_known_transport and has_opus:
        verdict = "adapter_candidate"
        recommendation = "Do not fork XiaoZhi core. Start with an external XiaoHong adapter/gateway and prove message, audio-frame, OTA and authentication compatibility."
        confidence = "medium" if len(records) >= 5 else "low"
    elif supports_known_transport:
        verdict = "transport_only_match"
        recommendation = "Transport is potentially reusable, but audio codec/frame settings and control messages are still unknown. Use a gateway spike, not a server fork."
        confidence = "low"
        risks.append("No Opus audio metadata was captured.")
    else:
        verdict = "insufficient_evidence"
        recommendation = "The capture has no recognised WebSocket, MQTT or UDP evidence. Capture network setup and the first dialogue turn."
        confidence = "low"

    if has_ws and not xiaozhi_path_seen:
        risks.append("WebSocket transport exists, but the XiaoZhi WebSocket path was not observed; endpoint compatibility is unproven.")
    if has_ws and xiaozhi_path_seen:
        risks.append("A XiaoZhi-like WebSocket path was observed, but message schema and authentication still need byte-level verification.")
    if not ota_path_seen:
        risks.append("OTA registration/update flow was not captured.")
    if not has_audio_evidence:
        risks.append("No audio metadata was captured; codec, sample rate and frame duration remain unknown.")
    if unsupported_transports:
        risks.append("Observed unsupported transports: " + ", ".join(unsupported_transports) + ".")

    next_checks.extend(
        [
            "Capture device registration / OTA request including headers and response body shape.",
            "Capture one full duplex dialogue: wake event, first control JSON, audio uplink frames, TTS downlink frames and stop/cancel event.",
            "Record audio codec, sample rate, channels, frame duration, packet framing and whether frames are encrypted.",
            "Record authentication material shape only (field names and token type); redact token values before committing captures.",
            "Map device capabilities: screen state, GPIO/button event, firmware version and acknowledgement messages.",
        ]
    )

    return {
        "capture_records": len(records),
        "observed": {
            "transports": transports,
            "endpoints": endpoints,
            "audio_codecs": codecs,
            "event_names": events,
            "message_kinds": dict(sorted(kinds.items())),
            "xiaozhi_websocket_path_seen": xiaozhi_path_seen,
            "xiaozhi_ota_path_seen": ota_path_seen,
            "mqtt_udp_pair_seen": has_mqtt_udp,
        },
        "assessment": {
            "verdict": verdict,
            "confidence": confidence,
            "recommendation": recommendation,
            "risks": _dedupe(risks),
            "next_checks": next_checks,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON array or JSON Lines network capture")
    parser.add_argument("--report", type=Path, help="Write JSON report to this file instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args(argv)

    try:
        report = analyze_records(load_capture(args.input))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
        print(f"Report written to {args.report}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
