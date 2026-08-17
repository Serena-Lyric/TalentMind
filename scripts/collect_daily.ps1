# 每日多源采集任务（D43）：信号 + HN 岗位 -> MySQL
# 用法（Windows 计划任务，管理员创建 SYSTEM 任务，**已实测验证**）：
#   schtasks /Create /F /SC DAILY /ST 02:00 /RU SYSTEM /TN "TalentMindCollect" /TR "'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File D:\Application\ClaudeCode\repository\TalentMind\scripts\collect_daily.ps1"
#   注意：Task To Run 必须用 powershell.exe 全路径（相对路径在 SYSTEM 任务下无法启动进程，2026-08-17 实测）
# 依赖：Docker(MySQL) 运行中；backend\.venv 已安装依赖；网络可访问 GitHub/HN/博客 RSS
# 日志：data\local\logs\collect_daily-YYYYMMDD.log（gitignore；重定向，避免计划任务下 Transcript 挂起）

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
$Backend = Join-Path $RepoRoot "backend"

# 日志前置：无论后续哪一步失败都有记录（含运行账户，便于定位 SYSTEM/用户上下文问题）
$LogDir = Join-Path $RepoRoot "data\local\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("collect_daily-" + (Get-Date -Format "yyyyMMdd") + ".log")
"[collect_daily] 启动: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') user=$env:USERNAME pwd=$(Get-Location)" | Add-Content $LogFile

if (-not (Test-Path $Python)) {
    "[collect_daily] 错误: 未找到 venv: $Python" | Add-Content $LogFile
    exit 1
}

Push-Location $Backend
try {
    & $Python -m app.collect.fetch_all *>&1 | Add-Content $LogFile
    $code = $LASTEXITCODE
} catch {
    $code = 1
    "[collect_daily] 异常: $($_.Exception.Message)" | Add-Content $LogFile
} finally {
    Pop-Location
}
if ($code -ne 0) {
    "[collect_daily] 失败，退出码 ${code}: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $LogFile
    exit $code
}
"[collect_daily] 完成: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $LogFile