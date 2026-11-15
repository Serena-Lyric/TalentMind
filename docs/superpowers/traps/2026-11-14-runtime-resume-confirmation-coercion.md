# 恢复确认值被布尔转换绕过

## 症状

`/collection/runtime/resume/{platform}` 接收 `{"confirmed":"false"}` 或 `{"confirmed":"0"}` 时，会把字符串当作已确认。`blocked` / `failed` 平台因此可能清除 STOP 并启动 worker，绕过人工恢复门禁。

## 根因

路由用 `bool(payload.get('confirmed', False))` 把任意 JSON 值转换成 Python 布尔值。非空字符串会变成 `True`；scheduler 本身的 `confirmed` 门禁没有问题，错误发生在 API 信任边界。

## 修复

路由仅接受 `type(confirmed) is bool`；缺省仍按 `False` 处理，其他值在调用 scheduler 前拒绝。真实 ASGI 回归覆盖 `blocked` / `failed`、字符串、数字、数组、对象、`null`、显式 `false` 与 `true`，并比较临时 SQLite 状态、STOP 文件、预检和 worker 副作用。

## 教训

人工确认是安全边界，必须保留 JSON 原始类型并严格校验。不能用通用 truthiness 转换代替调用方的显式确认；类型错误应在读取或修改运行状态之前 fail closed。
