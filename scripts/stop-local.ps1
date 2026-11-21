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
        # M1 已收敛为 runtime 单一入口；停止覆盖三站 worker 并等待进程树退出。
        $runtime = $null
        try { $runtime = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/runtime/status' -TimeoutSec 10 }
        catch { if ([int]$_.Exception.Response.StatusCode -ne 404) { throw } }
        if ($runtime) {
            if ($runtime.code -ne 0) { throw '无法核查持续采集状态，保留后端。' }
            $active = @($runtime.data.platforms.PSObject.Properties.Value | Where-Object { $_.status -in @('running','waiting') })
            if ($active.Count -gt 0) {
                $stop = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/runtime/stop' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 30
                if ($stop.code -ne 0) { throw '持续采集停止失败，保留后端。' }
                for ($attempt = 0; $attempt -lt 120; $attempt++) {
                    $runtime = Invoke-RestMethod -Uri 'http://127.0.0.1:18000/api/collection/runtime/status' -TimeoutSec 5
                    if ($runtime.code -ne 0) { throw '停止状态读取失败，保留后端。' }
                    $active = @($runtime.data.platforms.PSObject.Properties.Value | Where-Object { $_.status -in @('running','waiting') })
                    if ($active.Count -eq 0) { break }
                    Start-Sleep -Milliseconds 500
                }
                if ($active.Count -gt 0) { throw '采集子树尚在停止，保留后端；稍后重试。' }
            }
            $unresolved = @($runtime.data.platforms.PSObject.Properties.Value | Where-Object { $_.status -eq 'failed' -and $_.stop_reason -eq 'worker_termination_unconfirmed' })
            if ($unresolved.Count -gt 0) { throw '无法确认采集进程树退出，保留后端以便处理。' }
        }
    }
}
foreach ($entry in @($services.frontend, $services.backend.listener, $services.backend)) {
    if (-not $entry) { continue }
    $serviceProcess = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if ($serviceProcess -and $serviceProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$entry.started).ToUniversalTime().Ticks) { Stop-Process -Id $entry.pid -ErrorAction Stop }
}
Write-Host '已停止此入口启动的前后端；数据库容器与独立 Edge 保留。'
