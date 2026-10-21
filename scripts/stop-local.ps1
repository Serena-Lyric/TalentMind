$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $repoRoot 'data/local/local-runtime/services.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Host '没有此工作区的服务记录。'; exit 0 }
$services = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
if ($services.root -ne $repoRoot) { throw '服务记录不属于本工作区，拒绝停止。' }
# 先停止采集子任务，避免后端退出后遗留工作进程。
if ($services.backend) {
    $backendProcess = Get-Process -Id $services.backend.pid -ErrorAction SilentlyContinue
    if ($backendProcess -and $backendProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$services.backend.started).ToUniversalTime().Ticks) {
        $activeStatuses = @('preparing','waiting_for_browser','running','stopping','waiting_next_round')
        # 批次可能正在组合间等待；此时单项已结束，仍须先停止并归档批次。
        $batches = $null
        try { $batches = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/batches' -TimeoutSec 10 }
        catch { if ([int]$_.Exception.Response.StatusCode -ne 404) { throw } }
        if ($batches) {
            if ($batches.code -ne 0) { throw '无法核查批次状态，保留后端。' }
            foreach ($batch in @($batches.data.items | Where-Object { -not $_.finished_at -and $_.status -in @('running','waiting_next_round','stopping') })) {
                $batchUrl = "http://127.0.0.1:18000/api/collection/batches/$($batch.batch_id)"
                $reply = Invoke-RestMethod -Uri "$batchUrl/stop" -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 20
                if ($reply.code -ne 0) { throw '批次停止失败，保留后端。' }
                for ($attempt = 0; $attempt -lt 60; $attempt++) {
                    $batchState = Invoke-RestMethod -Uri $batchUrl -TimeoutSec 5
                    if ($batchState.code -ne 0) { throw '批次停止状态读取失败，保留后端。' }
                    if ($batchState.data.finished_at) { break }
                    Start-Sleep -Milliseconds 500
                }
                if (-not $batchState.data.finished_at) { throw '批次尚在停止或归档，保留后端；稍后重试。' }
            }
        }
        $status = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/status' -TimeoutSec 10
        if ($status.code -ne 0) { throw '无法核查任务状态，保留后端以便继续停止采集。' }
        if (-not $status.data.finished_at -and $status.data.status -in $activeStatuses) {
            $stop = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/stop' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 15
            if ($stop.code -ne 0) { throw '控制器拒绝停止任务，保留后端以便处理。' }
            for ($attempt = 0; $attempt -lt 60; $attempt++) {
                $status = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/status' -TimeoutSec 5
                if ($status.code -ne 0) { throw '停止状态读取失败，保留后端。' }
                if ($status.data.finished_at -or $status.data.status -notin $activeStatuses) { break }
                Start-Sleep -Milliseconds 500
            }
            if (-not $status.data.finished_at -and $status.data.status -in $activeStatuses) { throw '采集尚在停止/归档，保留后端；稍后重试。' }
        }
    }
}
foreach ($entry in @($services.frontend, $services.backend.listener, $services.backend)) {
    if (-not $entry) { continue }
    $serviceProcess = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if ($serviceProcess -and $serviceProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$entry.started).ToUniversalTime().Ticks) { Stop-Process -Id $entry.pid -ErrorAction Stop }
}
Write-Host '已停止此入口启动的前后端；数据库容器与独立 Edge 保留。'
