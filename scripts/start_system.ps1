# TalentMind 快速启动器
# 作用：双击 start_system.bat 后，依次完成
#   1) 确保 Docker 基础设施（MySQL/Neo4j/Redis）运行
#   2) 启动后端 FastAPI (18000)
#   3) 启动前端 Vite (18080)
#   4) 等待后端健康后打开浏览器
# 注意：本脚本【不启动数据采集程序】（采集由前端/人工控制）。
# 端口被占用时跳过对应服务（视为已在运行）。

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$LogDir = Join-Path $Root 'data\local\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackendOut = Join-Path $LogDir "backend-$Stamp.out.log"
$BackendErr = Join-Path $LogDir "backend-$Stamp.err.log"
$FrontendOut = Join-Path $LogDir "frontend-$Stamp.out.log"
$FrontendErr = Join-Path $LogDir "frontend-$Stamp.err.log"

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port([int]$Port, [int]$TimeoutSec = 90) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        if (Test-PortListening $Port) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host ''
Write-Host '=== TalentMind 快速启动 ===' -ForegroundColor Cyan
Write-Host "仓库根目录: $Root"

# ---- 1/5 Docker 基础设施 ----
Write-Host ''
Write-Host '[1/5] 检查 Docker 基础设施...'
$dockerOk = $false
try { docker info *> $null; $dockerOk = $true } catch { $dockerOk = $false }
if (-not $dockerOk) {
    Write-Host '  Docker 未运行，尝试启动 Docker Desktop...' -ForegroundColor Yellow
    $dd = @("$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
            "$env:LOCALAPPDATA\Docker\Docker Desktop.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($dd) { Start-Process $dd } else { Write-Host '  未找到 Docker Desktop，请手动启动后重试' -ForegroundColor Red }
    for ($i = 0; $i -lt 45; $i++) {
        try { docker info *> $null; $dockerOk = $true; break } catch { Start-Sleep -Seconds 2 }
    }
}
if ($dockerOk) {
    Write-Host '  Docker OK，检查容器...' -ForegroundColor Green
    $composePs = docker compose ps 2>$null
    if ($composePs -notmatch 'Up') {
        Write-Host '  启动 MySQL/Neo4j/Redis 容器...'
        docker compose up -d 2>&1 | Out-Host
    } else {
        Write-Host '  容器已在运行' -ForegroundColor Green
    }
    if (-not (Wait-Port 3306 120)) {
        Write-Host '  [WARN] MySQL 端口 3306 未就绪（容器可能仍在启动）' -ForegroundColor Yellow
    } else {
        Write-Host '  MySQL/Neo4j/Redis 就绪' -ForegroundColor Green
    }
} else {
    Write-Host '  [WARN] Docker 不可用，继续尝试启动后端/前端（数据库可能不可达）' -ForegroundColor Yellow
}

# ---- 2/5 后端 ----
Write-Host ''
Write-Host '[2/5] 启动后端 FastAPI (18000)...'
$Py = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (Test-PortListening 18000) {
    Write-Host '  18000 已被占用，视为后端已在运行' -ForegroundColor Green
} elseif (Test-Path $Py) {
    Start-Process -FilePath $Py -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18000' -WorkingDirectory (Join-Path $Root 'backend') -WindowStyle Hidden -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr
    Write-Host "  已启动，日志: $BackendOut" -ForegroundColor Green
} else {
    Write-Host '  未找到 backend\.venv，请先完成环境安装（见 README）' -ForegroundColor Red
}

# ---- 3/5 前端 ----
Write-Host ''
Write-Host '[3/5] 启动前端 Vite (18080)...'
if (Test-PortListening 18080) {
    Write-Host '  18080 已被占用，视为前端已在运行' -ForegroundColor Green
} else {
    Start-Process -FilePath 'pnpm.cmd' -ArgumentList 'exec','vite','--host','127.0.0.1','--port','18080' -WorkingDirectory (Join-Path $Root 'frontend') -WindowStyle Hidden -RedirectStandardOutput $FrontendOut -RedirectStandardError $FrontendErr
    Write-Host "  已启动，日志: $FrontendOut" -ForegroundColor Green
}

# ---- 4/5 等待后端就绪 ----
Write-Host ''
Write-Host '[4/5] 等待后端就绪...'
$healthOk = $false
for ($i = 0; $i -lt 60; $i++) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect('127.0.0.1', 18000)
        $healthOk = $true
    } catch { }
    $client.Close()
    if ($healthOk) { break }
    Start-Sleep -Seconds 2
}
if ($healthOk) {
    Write-Host '  后端端口就绪' -ForegroundColor Green
} else {
    Write-Host '  [WARN] 后端未就绪，请查看日志' -ForegroundColor Yellow
}

# ---- 5/5 打开浏览器 ----
Write-Host ''
Write-Host '[5/5] 打开系统页面...' -ForegroundColor Cyan
Write-Host '  前端: http://127.0.0.1:18080/'
Write-Host '  后端: http://127.0.0.1:18000/health'
Write-Host '  Neo4j Browser: http://127.0.0.1:7474/'
explorer.exe 'http://127.0.0.1:18080/'
Write-Host ''
Write-Host '=== 启动完成 ===' -ForegroundColor Cyan
