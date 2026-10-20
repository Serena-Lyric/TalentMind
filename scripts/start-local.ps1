param([switch]$NoBrowser, [string]$RealGraphDirectory)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot 'data/local/local-runtime'
$stateFile = Join-Path $runtimeDir 'services.json'
$pythonExe = Join-Path $repoRoot 'backend/.venv/Scripts/python.exe'
$viteEntry = Join-Path $repoRoot 'frontend/node_modules/vite/bin/vite.js'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

# 只接受本入口保存的同一进程实例；占用端口不能证明服务健康。
function Test-OwnedService($entry) {
    if (-not $entry) { return $false }
    $serviceProcess = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    return $serviceProcess -and $serviceProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$entry.started).ToUniversalTime().Ticks
}

function Assert-ListenerOwner([int]$Port, $entry) {
    if (-not (Test-OwnedService $entry)) { throw "服务进程已退出：$Port" }
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if (-not $listeners.Count) { throw "没有监听进程：$Port" }
    foreach ($listener in $listeners) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($listener.OwningProcess -ne $entry.pid -and $owner.ParentProcessId -ne $entry.pid) { throw "端口 $Port 的响应不属于本入口进程，拒绝记录 PID $($listener.OwningProcess)。" }
    }
}

function Wait-Response([string]$Url, $entry) {
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        if (-not (Test-OwnedService $entry)) { throw "服务已退出: $Url；日志位于 $runtimeDir" }
        try { return Invoke-RestMethod -Uri $Url -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 500 }
    }
    throw "健康检查超时: $Url；日志位于 $runtimeDir"
}

$saved = if (Test-Path -LiteralPath $stateFile) { Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json -AsHashtable } else { $null }
if ($saved -and $saved.root -ne $repoRoot) { throw '服务记录不属于本工作区，拒绝复用。' }
if (-not $PSBoundParameters.ContainsKey('RealGraphDirectory')) { $RealGraphDirectory = $saved.previewDir }
if ($RealGraphDirectory) {
    $RealGraphDirectory = (Resolve-Path -LiteralPath $RealGraphDirectory).Path
    if (-not (Test-Path -LiteralPath (Join-Path $RealGraphDirectory 'manifest.json'))) { throw '真实图预览目录缺少 manifest.json' }
}
if ((Test-OwnedService $saved.frontend) -and $saved.previewDir -ne $RealGraphDirectory) { throw '真实图预览目录已改变；请先运行 stop-local.ps1 再启动。' }
foreach ($port in @(18000, 18080)) {
    $entry = if ($port -eq 18000) { $saved.backend } else { $saved.frontend }
    $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    $foreign = @($listeners | Where-Object {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)"
        $_.OwningProcess -ne $entry.pid -and $owner.ParentProcessId -ne $entry.pid
    })
    if ($listeners.Count -and (-not (Test-OwnedService $entry) -or $foreign.Count)) {
        throw "端口 $port 被其他进程占用（PID $($listeners.OwningProcess -join ',')）。未停止或复用其他服务。"
    }
}
if (-not (Test-Path -LiteralPath $pythonExe)) { throw '缺少 backend/.venv：执行 python -m venv backend/.venv 并安装 backend/requirements.txt' }
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'backend/.env'))) { throw '缺少 backend/.env；复制 .env.example 后配置本机数据库，勿覆盖已有配置。' }
if (-not (Test-Path -LiteralPath $viteEntry)) { throw '缺少前端依赖：执行 pnpm --dir frontend install --frozen-lockfile' }
$nodeExe = (Get-Command node -ErrorAction Stop).Source

# 仅启动原有容器，不创建卷、不迁移或导入数据。
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:ProgramFiles 'Docker/Docker/Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $dockerDesktop)) { throw 'Docker 未运行且未找到 Docker Desktop。请先启动数据库运行环境。' }
    Write-Host '正在启动 Docker Desktop…'
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 1
        & docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop 未在60秒内就绪；前后端尚未启动。' }
}
foreach ($containerName in @('talentmind-mysql-1', 'talentmind-neo4j-1', 'talentmind-redis-1')) {
    $running = & docker inspect --format '{{.State.Running}}' $containerName 2>$null
    if ($LASTEXITCODE -ne 0) { throw "缺少既有容器 $containerName；未创建新容器或数据卷。请核对本机环境。" }
    if ($running -eq 'false') {
        & docker start $containerName | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "容器无法启动: $containerName" }
    }
}
$services = @{ root = $repoRoot; backend = $saved.backend; frontend = $saved.frontend; previewDir = $RealGraphDirectory }
try {
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:TALENTMIND_LOCAL_RAW = '1'
    $env:VITE_PROXY_TARGET = 'http://127.0.0.1:18000'
    if ($RealGraphDirectory) { $env:M3_REAL_PREVIEW_DIR = $RealGraphDirectory } else { Remove-Item Env:M3_REAL_PREVIEW_DIR -ErrorAction SilentlyContinue }
    if (-not (Test-OwnedService $services.backend)) {
        $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 18000' -WorkingDirectory (Join-Path $repoRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'backend.out.log') -RedirectStandardError (Join-Path $runtimeDir 'backend.err.log')
        $services.backend = @{ pid = $backendProcess.Id; started = $backendProcess.StartTime.ToUniversalTime().ToString('o') }
    }
    $services | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding utf8
    $health = Wait-Response 'http://127.0.0.1:18000/health' $services.backend
    if ($health.code -ne 0 -or $health.data.status -ne 'up') { throw '后端 /health 返回异常' }
    Assert-ListenerOwner 18000 $services.backend
    $backendListener = Get-Process -Id (Get-NetTCPConnection -LocalPort 18000 -State Listen).OwningProcess
    $services.backend.listener = @{ pid = $backendListener.Id; started = $backendListener.StartTime.ToUniversalTime().ToString('o') }
    if (-not (Test-OwnedService $services.frontend)) {
        $frontendProcess = Start-Process -FilePath $nodeExe -ArgumentList "`"$viteEntry`" --host 127.0.0.1 --port 18080 --strictPort" -WorkingDirectory (Join-Path $repoRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'frontend.out.log') -RedirectStandardError (Join-Path $runtimeDir 'frontend.err.log')
        $services.frontend = @{ pid = $frontendProcess.Id; started = $frontendProcess.StartTime.ToUniversalTime().ToString('o') }
    }
    $services | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding utf8
    $database = Wait-Response 'http://127.0.0.1:18080/api/collection/database-stats' $services.frontend
    Assert-ListenerOwner 18080 $services.frontend
    if ($database.code -ne 0 -or $database.data.available -eq $false -or $null -eq $database.data.database_total) { throw '前端代理已响应，但数据库读取失败：检查 backend/.env 的 MYSQL_URL（本机端口23306）与 backend.err.log' }
    Write-Host 'TalentMind 已就绪： http://127.0.0.1:18080/#/collection'
    Write-Host "后端健康： http://127.0.0.1:18000/health；真实 JD 数：$($database.data.database_total)"
    Write-Host "日志：$runtimeDir；停止：pwsh -File `"$PSScriptRoot/stop-local.ps1`""
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:18080/#/collection' }
} catch {
    Write-Error "启动失败：$($_.Exception.Message)；进程记录保存在 $stateFile，可运行 stop-local.ps1 精确停止。"
    exit 1
}
