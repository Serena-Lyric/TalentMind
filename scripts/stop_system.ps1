# TalentMind 快速关闭器
# 作用：双击 stop_system.bat 后，依次完成
#   1) 停止后端 FastAPI (18000)
#   2) 停止前端 Vite (18080)
#   3) 停止 Docker 容器（MySQL/Neo4j/Redis，命名卷数据保留，不退出 Docker Desktop）
# 说明：本脚本与 start_system.ps1 配套，按监听端口定位进程
#   （Get-NetTCPConnection + Stop-Process，AGENTS 平台 API 规则，不用文本解析）。
#   - 若后端/前端是在终端手动启动，请先在对应终端按 Ctrl+C；端口仍被占用时本脚本兜底清理。
#   - 附加参数 -KeepDocker：跳过第 3 步（保留 MySQL/Neo4j/Redis 容器继续运行）。

param(
    [switch]$KeepDocker
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 停止监听指定端口的进程；无进程时静默返回
function Stop-ListeningProcess([int]$Port, [string]$Label) {
    $pids = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -gt 0 })
    if ($pids.Count -eq 0) {
        Write-Host "  $Label ($Port) 未在运行" -ForegroundColor DarkGray
        return
    }
    foreach ($ProcId in $pids) {
        $proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
        $procName = if ($proc) { $proc.ProcessName } else { "PID $ProcId" }
        Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
        Write-Host "  已停止 $Label ($Port): $procName (PID $ProcId)" -ForegroundColor Green
    }
    # 等待端口释放（最多 10 秒）
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt 10) {
        if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 300
    }
}

Write-Host ''
Write-Host '=== TalentMind 快速关闭 ===' -ForegroundColor Cyan
Write-Host "仓库根目录: $Root"

# ---- 1/3 后端 ----
Write-Host ''
Write-Host '[1/3] 停止后端 FastAPI (18000)...'
Stop-ListeningProcess -Port 18000 -Label '后端'

# ---- 2/3 前端 ----
Write-Host ''
Write-Host '[2/3] 停止前端 Vite (18080)...'
Stop-ListeningProcess -Port 18080 -Label '前端'

# ---- 3/3 Docker 容器 ----
Write-Host ''
if (-not $KeepDocker) {
    Write-Host '[3/3] 停止 Docker 容器 (MySQL/Neo4j/Redis)...'
    $dockerOk = $false
    try { docker info *> $null; $dockerOk = $true } catch { $dockerOk = $false }
    if (-not $dockerOk) {
        Write-Host '  Docker 不可用，跳过' -ForegroundColor Yellow
    } else {
        $composePs = docker compose ps 2>$null
        if ($composePs -match 'Up') {
            docker compose stop 2>&1 | Out-Host
            Write-Host '  容器已停止（数据保留在命名卷，Docker Desktop 未退出）' -ForegroundColor Green
        } else {
            Write-Host '  无运行中的容器，跳过' -ForegroundColor Green
        }
    }
} else {
    Write-Host '[3/3] 已按 -KeepDocker 跳过 Docker 停止' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '=== 关闭完成 ===' -ForegroundColor Cyan
Write-Host '再次使用请双击 start_system.bat（自动重新拉起 Docker 容器与前后端）'