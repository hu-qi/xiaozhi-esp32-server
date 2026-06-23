#!/usr/bin/env python3
"""Read-only API smoke probe for an AuraAudio/XiaoHong console deployment.

The tool is intentionally limited to safe GET requests. It confirms the
management/control plane exposed by a deployment without uploading firmware,
changing models, mutating agents, or binding devices.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 10.0
TOKEN_ENV = "AURAAUDIO_TOKEN"
SENSITIVE_KEY_NAMES = {"token", "password", "authorization", "secret", "clienthash", "cookie"}


@dataclass(frozen=True)
class Probe:
    name: str
    path: str
    authenticated: bool = True


def _normalise_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise ValueError("base URL must not be empty")
    if not value.startswith(("http://", "https://")):
        raise ValueError("base URL must start with http:// or https://")
    return value


def _redacted_data_summary(data: Any) -> dict[str, Any]:
    """Return structure-only diagnostics without echoing secrets or user data."""
    if isinstance(data, dict):
        safe_keys = [
            str(key)
            for key in data.keys()
            if str(key).casefold() not in SENSITIVE_KEY_NAMES
        ]
        result: dict[str, Any] = {
            "kind": "object",
            "keys": sorted(safe_keys)[:20],
        }
        if isinstance(data.get("list"), list):
            result["list_count"] = len(data["list"])
        if isinstance(data.get("board"), str):
            result["board"] = data["board"]
        if isinstance(data.get("appVersion"), str):
            result["app_version"] = data["appVersion"]
        return result
    if isinstance(data, list):
        return {"kind": "array", "count": len(data)}
    if data is None:
        return {"kind": "null"}
    return {"kind": type(data).__name__}


def _request_json(
    opener: Callable[..., Any],
    url: str,
    token: str | None,
    timeout: float,
) -> tuple[int, dict[str, Any] | None, str | None]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, _parse_json(raw), None
    except URLError as exc:
        return 0, None, f"network error: {exc.reason}"
    except OSError as exc:
        return 0, None, f"request error: {exc}"

    payload = _parse_json(raw)
    if payload is None:
        return status, None, "response is not valid JSON"
    return status, payload, None


def _parse_json(raw: str) -> dict[str, Any] | None:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else {"data": decoded}


def build_probes(agent_id: str | None) -> list[Probe]:
    probes = [
        Probe("public_config", "/user/pub-config", authenticated=False),
        Probe("current_user", "/user/info"),
        Probe("agent_list", "/agent/list?" + urlencode({"page": 1, "limit": 1})),
        Probe("firmware_type_dictionary", "/admin/dict/data/type/FIRMWARE_TYPE"),
    ]
    if agent_id:
        probes.extend(
            [
                Probe("agent_detail", f"/agent/{agent_id}"),
                Probe("bound_devices", f"/device/bind/{agent_id}"),
            ]
        )
    return probes


def run_probes(
    base_url: str,
    token: str | None,
    agent_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    base_url = _normalise_base_url(base_url)
    results: list[dict[str, Any]] = []
    for probe in build_probes(agent_id):
        if probe.authenticated and not token:
            results.append(
                {
                    "name": probe.name,
                    "path": probe.path,
                    "skipped": True,
                    "reason": f"missing {TOKEN_ENV}",
                }
            )
            continue
        status, payload, error = _request_json(
            opener, f"{base_url}{probe.path}", token if probe.authenticated else None, timeout
        )
        item: dict[str, Any] = {
            "name": probe.name,
            "path": probe.path,
            "http_status": status,
            "ok": bool(status and 200 <= status < 300 and error is None),
        }
        if error:
            item["error"] = error
        if payload is not None:
            item["api_code"] = payload.get("code")
            item["message"] = payload.get("msg")
            item["data"] = _redacted_data_summary(payload.get("data"))
        results.append(item)

    passed = sum(1 for result in results if result.get("ok"))
    return {
        "base_url": base_url,
        "mode": "read_only",
        "passed": passed,
        "total": len(results),
        "results": results,
        "next_step": (
            "Management/control-plane endpoints are observable. This does not "
            "validate the device realtime audio/session protocol; capture that "
            "separately before implementing a device adapter."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="Console API prefix, for example https://host/xiaohong",
    )
    parser.add_argument(
        "--token",
        default=os.getenv(TOKEN_ENV),
        help=f"Bearer token; defaults to ${TOKEN_ENV}. Avoid shell history when possible.",
    )
    parser.add_argument("--agent-id", help="Optionally inspect one agent and its bound devices.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        report = run_probes(args.base_url, args.token, args.agent_id, args.timeout)
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
