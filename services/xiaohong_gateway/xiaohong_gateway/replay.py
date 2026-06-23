"""Offline replay harness for captured XiaoHong sessions.

This is the first runnable gateway entry point. A transport listener can later
convert WebSocket/MQTT frames into DeviceEnvelope objects and reuse this exact
state machine.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from .contracts import DeviceEnvelope
from .session import GatewaySession
from .translator import XiaoHongTranslator


def load_records(path: Path) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"record on line {line_number} must be an object")
        yield record


def envelope_from_record(record: dict[str, Any]) -> DeviceEnvelope:
    direction = record.get("direction", "device_to_cloud")
    if direction not in {"device_to_cloud", "cloud_to_device"}:
        raise ValueError(f"invalid direction: {direction}")
    kind = record.get("kind", "unknown")
    if kind not in {"text", "binary", "unknown"}:
        kind = "unknown"
    payload = record.get("payload")
    audio = record.get("audio")
    return DeviceEnvelope(
        direction=direction,
        kind=kind,
        payload=payload if isinstance(payload, dict) else {},
        audio=audio if isinstance(audio, dict) else {},
        raw_size=int(record.get("raw_size") or 0),
    )


def replay(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    session = GatewaySession(XiaoHongTranslator())
    output: list[dict[str, Any]] = []
    for sequence, record in enumerate(records, start=1):
        result = session.process(envelope_from_record(record))
        item: dict[str, Any] = {
            "sequence": sequence,
            "accepted": result.accepted,
            "state": session.state.value,
        }
        if result.event:
            item["event"] = {
                "name": result.event.name,
                "device_id": result.event.device_id,
                "data": result.event.data,
            }
        if result.reason:
            item["reason"] = result.reason
        output.append(item)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Redacted JSON Lines capture")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = replay(load_records(args.input))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if all(item["accepted"] for item in output) else 1


if __name__ == "__main__":
    raise SystemExit(main())
