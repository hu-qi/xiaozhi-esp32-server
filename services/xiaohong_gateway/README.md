# XiaoHong Gateway（协议适配 Spike）

这是小鸿设备与 `xiaozhi-esp32-server` / XiaoHong Hub 之间的**独立协议边界**。

它不是第二套智控台，也不复制 Agent、知识库、设备绑定或 OTA 后台。AuraAudio
探索结果已表明这些管理能力可以由小智服务端复用；Gateway 只解决小鸿实时端侧协议
可能与小智客户端不一致的问题。

```text
XiaoHong OpenHarmony / WS63
  wake word · audio · display · GPIO · button
          ↓  actual device protocol
XiaoHong Gateway
  transport listener · auth adapter · frame translator · session guard
          ↓  canonical events
xiaozhi-esp32-server / XiaoHong Hub
  Agent · ASR/TTS · MCP · device control plane · audit
```

## 当前已实现

- 可配置的协议 Profile；
- 端侧消息到统一事件的保守翻译；
- 单连接会话状态机；
- 注册前拦截音频/控制消息；
- 连接内设备身份锁定；
- 脱敏 JSONL 会话离线回放。

## 当前刻意未实现

- 监听真实 WebSocket / MQTT / UDP；
- 冒充 AuraAudio 或转发真实生产 token；
- 未经过真实采集证明的 JSON 字段、音频封包、OTA 流程；
- 任何 Agent 写文件、推送、部署等高风险动作。

这是为了避免“协议还没抓到，服务已经写死了错误假设”。

## 本地验证

```bash
cd services/xiaohong_gateway
python3 -m unittest discover -s tests -v
```

将真实设备会话脱敏成 JSONL 后回放：

```bash
python3 -m xiaohong_gateway.replay --input ./capture.redacted.jsonl --pretty
```

单条记录格式：

```json
{"direction":"device_to_cloud","kind":"text","payload":{"type":"hello","device_id":"AA:BB","board":"xiaohong_v1"}}
{"direction":"device_to_cloud","kind":"binary","audio":{"codec":"opus","sample_rate":16000,"channels":1,"frame_ms":60},"raw_size":480}
```

## 真实协议接入顺序

1. 补一轮真实的注册、首条控制包、上/下行音频、打断和能力 ACK 采集。
2. 将真实事件名填入 `ProtocolProfile`，为每个设备端版本建 profile。
3. 编写 `WebSocketListener` 或 `MqttUdpListener`，将原始帧解码为 `DeviceEnvelope`。
4. 将 `CanonicalEvent` 路由到小智实时协议适配器或 XiaoHong Hub。
5. 最后才接屏幕状态、GPIO 按键和实体确认动作。

## 安全约束

- 不将真实 Bearer token、设备 MAC、Wi-Fi 密码、音频内容提交到仓库。
- Gateway 只接受私网或经过 mTLS / 配对的设备连接。
- 高风险 Agent 动作必须由小鸿实体按键确认；Gateway 只转发确认事件，不直接执行部署或删除。
