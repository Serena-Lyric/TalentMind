# BOSS CDP 连接层兼容设计（2026-08-20）

## 背景与目标

用户已经在独立 Edge 用户目录中人工登录 BOSS 求职端（“我要投职”）。当前采集业务能够通过标准 CDP `/json/list` 连接页面，但 Edge 的 `DevToolsActivePort` 显示动态端口（曾出现 `3180`），而默认 `9222` 未监听。目标是在不接触账号、密码、验证码、Cookie、不绕过登录/反爬的前提下，让采集模块自动发现并附加到已登录的 BOSS 页面。

## 方案比较

1. **继续只使用固定 `9222/json/list`**：改动最小，但无法处理 Edge 动态端口和浏览器级 WebSocket，不能解决当前问题。
2. **读取 `DevToolsActivePort`，兼容标准 HTTP 发现和浏览器级 WebSocket（推荐）**：优先兼容现有 `/json/list`；失败时从用户目录读取端口与浏览器 WebSocket 路径，通过 `Target.getTargets` 选择页面并 `Target.attachToTarget`，保留现有 `Runtime.evaluate`、`Page.navigate` 业务接口。改动集中、可测试，且不依赖 CC Switch。
3. **逆向 Edge `edge://inspect` / 3180 专有入口**：入口当前没有稳定的 `/json/list` 或 `/json/version` 协议，协议不明确且可能随版本变化；本次不采用，避免把非标准中转接口写入正式采集链路。

## 设计

### 端点发现

- `--cdp` 继续接受 HTTP CDP 地址，也接受直接的 `ws://` 浏览器 WebSocket 地址。
- 新增可选 `--user-data-dir`。当 HTTP 端点不可用时，从 `<user-data-dir>/DevToolsActivePort` 读取端口和 WebSocket 路径，并请求该端口的 `/json/list`、`/json/version`。
- 标准页面 WebSocket 继续直接连接；只有拿到浏览器级 WebSocket 时才走目标发现/附加。
- 可选 `target_url_contains` 用于优先选择 `zhipin.com` 页面，避免附加到 `edge://` 或空白页。

### 浏览器级 CDP

- 连接浏览器 WebSocket 后调用 `Target.getTargets`。
- 选择 `type=page` 且 URL 匹配目标条件的页面；若没有匹配项，回退到第一个页面。
- 调用 `Target.attachToTarget(flatten=true)` 获得 `sessionId`。
- 后续 CDP 命令带 `sessionId`，对调用方保持 `evaluate`、`navigate`、`close` API 不变。

### 安全与失败行为

- 不尝试启动、注入或接管用户浏览器；只连接用户显式启动的调试端点。
- 3180/15721 不被硬编码为 CC Switch 或 Edge 专有采集通道；HTTP 端点不可用时给出包含用户目录和 `DevToolsActivePort` 的可操作错误。
- BOSS 登录页、验证码和反爬检测逻辑保持不变。
- 连接失败、端点文件过期或页面不存在时快速失败，不把快照数据冒充模块采集结果。

### 测试与验收

- 覆盖 `DevToolsActivePort` 读取、页面目标筛选和浏览器级 `Target` 附加消息格式。
- 保持现有 BOSS 归一化测试和后端全量测试通过。
- 用户重新启动独立 Edge 后，先执行 Python/北京一页冒烟采集，再扩大关键词、城市、页数和详情；成功后人工注销并记录时间。
