# Edge CDP 端口落入 Windows 排除段（2026-08-20）

## 症状

Edge 主进程命令行包含 `--remote-debugging-port=9222`，但 `127.0.0.1:9222/json/version` 始终拒绝连接；目标用户目录中的旧 `DevToolsActivePort` 记录了不可用的 3180。

## 根因

Windows TCP 排除端口范围包含 `9181-9280`，因此 9222 无监听者时仍不能被新进程绑定。仅查看 Edge 命令行或 `Get-NetTCPConnection` 会误以为参数正确且端口空闲；实际 socket bind 会返回 WinError 10013。

## 修复

不修改系统端口排除策略，也不把 CC Switch 的 15721 或 Edge 专有 3180 当作 CDP。选择排除范围之外且已实测可绑定的 9333，要求用户关闭目标独立 Edge 后使用同一用户目录以 `--remote-debugging-port=9333` 重启；采集模块通过 `--cdp http://127.0.0.1:9333` 连接。

## 教训

CDP 端口诊断必须同时检查监听状态和端口绑定权限；“无监听”不等于“可用”。在 Windows 上应避开系统排除段，并在运行手册中给出可验证的备用端口。
