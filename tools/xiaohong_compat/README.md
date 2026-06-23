# XiaoHong compatibility probe

This tool turns a redacted XiaoHong cloud traffic capture into a conservative
recommendation for the next engineering step. It does **not** assert that the
XiaoZhi service can be reused merely because both implementations use Wi-Fi,
WebSocket or Opus.

## Capture format

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

## Run

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
