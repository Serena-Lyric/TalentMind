# Edge CDP 动态端口与过期 DevToolsActivePort（2026-08-20）

## 症状

Edge 进程参数包含 `--remote-debugging-port=9222`，但 `127.0.0.1:9222` 拒绝连接；用户曾在 `edge://inspect` 看到动态端口 `3180`。用户目录中的 `DevToolsActivePort` 文件却仍记录旧端口和旧浏览器 WebSocket 路径。

## 根因

Edge 的调试端口可能不是固定的 9222；`DevToolsActivePort` 是浏览器启动时生成的动态发现文件，浏览器重启后旧文件可能暂时保留。CC Switch 的 `127.0.0.1:15721` 健康接口不是 CDP，不能用 `/json/list` 方式连接。

## 修复

`backend/app/collect/fetchers/cdp.py` 保留标准 `/json/list`，并在指定 `--user-data-dir` 时读取当前 `DevToolsActivePort`；同时支持浏览器级 WebSocket，通过 `Target.getTargets` 选择 BOSS 页面、`Target.attachToTarget(flatten=true)` 获取 session，再复用原有 `Runtime.evaluate` 和 `Page.navigate`。连接层不逆向 3180 专有入口、不把 15721 当作 CDP。

## 教训

不要把命令行参数中的固定端口当作真实监听端口；应优先检查用户目录中的调试发现文件，并验证端口属于当前 Edge 进程。过期发现文件只能作为候选，连接失败必须清晰报告并要求用户重启独立 Edge。
