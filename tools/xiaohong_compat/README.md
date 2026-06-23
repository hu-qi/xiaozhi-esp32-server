# XiaoHong compatibility probes

This directory contains two separate probes because cloud-console compatibility
and realtime device-session compatibility are different questions:

1. `probe_console_api.py` confirms the **management/control plane** with
   read-only API calls.
2. `analyze_capture.py` evaluates a redacted **realtime device traffic** capture
   and produces a conservative adapter recommendation.

Neither probe asserts that the XiaoZhi service can be reused merely because both
implementations use Wi-Fi, WebSocket or Opus.

## 1. Verify the AuraAudio control plane

The API probe makes only `GET` requests. It never uploads firmware, changes an
Agent, updates a model or binds/unbinds a device. Keep the token in an
environment variable rather than command history:

```bash
export AURAAUDIO_TOKEN='replace-with-your-token'

python3 tools/xiaohong_compat/probe_console_api.py \
  --base-url 'https://your-console.example/xiaohong' \
  --agent-id 'optional-agent-id' \
  --pretty
```

It checks the public configuration plus, when a token is present:

- current user;
- Agent list;
- firmware type dictionary, including whether `xiaohong_v1` is exposed;
- optionally, one Agent and its bound-device list.

Output contains response status, API code and redacted data shape only. Token,
password, cookie, secret and client hash fields are not printed.

A successful result verifies the management/control plane only. It does **not**
verify OTA request compatibility or the realtime audio/control protocol.

## 2. Analyse a realtime capture

Provide either a JSON array or JSON Lines file. Every record should include the
following fields where available:

```json
{
  "ts": "2026-06-23T12:00:00Z",
  "direction": "device_to_cloud",
  "transport": "wss",
  "endpoint": "wss://cloud.example/v1/session",
  "kind": "text",
  "payload": {"type": "hello"},
  "audio": {"codec": "opus", "sample_rate": 16000, "channels": 1, "frame_ms": 60}
}
```

Redact device IDs, tokens, cookies, Wi-Fi credentials and audio content before
saving a capture. Keep field names, endpoint paths, message types and audio
metadata intact.

```bash
python3 tools/xiaohong_compat/analyze_capture.py \
  --input tools/xiaohong_compat/tests/fixtures/xiaohong_ws_opus.jsonl \
  --pretty

python3 -m unittest discover -s tools/xiaohong_compat/tests -v
```

## Decision rule

- `adapter_candidate`: a supported transport and Opus evidence were observed;
  implement an external gateway first.
- `transport_only_match`: a transport matches but audio/control details are
  missing; run a gateway spike only.
- `separate_cloud_or_protocol_gateway`: the capture shows only unsupported
  transports; keep XiaoHong cloud/client work separate.
- `insufficient_evidence`: the capture cannot support an architecture decision.

The report deliberately never returns "native compatible". Authentication,
control JSON, audio frame layout, OTA registration and device capability
acknowledgements must still be validated.
