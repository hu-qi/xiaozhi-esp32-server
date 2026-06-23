# XiaoHong × XiaoZhi：服务层复用决策记录

**状态：待协议采集验证；当前不分叉 XiaoZhi 核心。**

## 已知事实

- XiaoHong 是 WS63 + OpenHarmony 的 RISC-V 设备，公开资料表明其端侧具备
  Wi-Fi、BLE、NearLink、Opus 音频、屏幕与 GPIO/I²C/UART 扩展能力。
- `xiaozhi-esp32-server` 是按小智通信协议实现的后端，提供 WebSocket 与
  MQTT+UDP 接入、OTA、音频交互、设备管理、MCP 与插件机制。
- 芯片、RTOS 和硬件驱动不同，并不能直接推出云端不能复用；反过来，均使用
  WebSocket 或 Opus 也不能推出协议兼容。

## 结论

不维护长期 `xiaohong` 分支。采用三层仓库边界：

1. **小鸿端**：在 `xiaohong-ai` 的 OpenHarmony / BSP 仓库或独立 overlay 中维护，
   负责唤醒、音频、屏幕、GPIO、配网和端侧协议。
2. **小智 fork**：保持接近上游。只有在协议验证后，才增加一个可插拔的
   `xiaohong` adapter；不得把 OpenHarmony 驱动、板级逻辑或 Agent 业务塞入核心。
3. **XiaoHong Hub（独立仓库）**：负责 Coding Agent、实体确认、设备能力模型、
   场景编排、审计和小鸿 ↔ 小智/其他云的桥接。

## 路径选择

| 采集结果 | 实施方式 |
| --- | --- |
| 认证、控制 JSON、Opus 帧、OTA 全部与小智一致 | 在小智 fork 新增小鸿设备 profile / adapter，设备端单独维护 |
| WebSocket 或 MQTT+UDP、Opus 大致一致，但消息或鉴权不同 | 新建独立 `xiaohong-gateway`，在边界翻译协议；不改小智核心 |
| 只发现自定义/不支持的传输或闭源云协议 | 小鸿云端与端侧独立，Hub 通过业务 API/插件与其集成 |

## 当前分支用途

`chore/xiaohong-compatibility-baseline` 只放协议采集与判定工具，不承诺运行时
兼容性。待完成真实设备会话采集后，再创建短生命周期的
`spike/xiaohong-protocol-adapter` 分支验证适配器。

## 必采数据

1. 开机后配网、设备注册、OTA 请求/响应。
2. 唤醒后的一轮完整语音会话：首个控制包、上行音频、下行 TTS、结束/打断。
3. 音频编码、采样率、帧时长、二进制包封装、加密方式。
4. 屏幕状态、按键/GPIO 事件、能力上报与 ACK。
5. 认证字段名称与令牌类型（只保留字段名和长度，严禁提交真实令牌）。
