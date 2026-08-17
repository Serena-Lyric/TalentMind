# 每日多源采集任务（D41）：信号 + HN 岗位 -> MySQL
# 用法（Windows 计划任务）：
#   schtasks /Create /F /SC DAILY /ST 02:00 /TN "TalentMindCollect" /TR "'powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\Application\ClaudeCode\repository\TalentMind\scripts\collect_daily.ps1'"
# 依赖：Docker(MySQL) 运行中；backend\.venv 已安装依赖；网络可访问 GitHub/HN/博客 RSS
# 日志：data\local\logs\collect_daily-YYYYMMDD.log（gitignore；用重定向，避免计划任务下 Start-Transcript 挂起）

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
$Backend = Join-Path $RepoRoot "backend"

if (-not (Test-Path $Python)) {
    Write-Error "未找到 venv: $Python"
    exit 1
}

$LogDir = Join-Path $RepoRoot "data\local\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("collect_daily-" + (Get-Date -Format "yyyyMMdd") + ".log")

"[collect_daily] 开始采集: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $LogFile
Push-Location $Backend
try {
    & $Python -m app.collect.fetch_all *>&1 | Add-Content $LogFile
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) {
    "[collect_daily] 失败，退出码 ${code}: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $LogFile
    exit $code
}
"[collect_daily] 完成: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $LogFile