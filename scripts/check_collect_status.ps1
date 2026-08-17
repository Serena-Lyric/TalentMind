# 采集状态一键查看（TalentMind 运维用）
# 输出：1) 定时任务状态 2) 最近采集日志 3) 数据库采集量
# 用法：powershell -ExecutionPolicy Bypass -File scripts\check_collect_status.ps1

$ErrorActionPreference = "Stop"
# PowerShell 7+ 默认把 native stderr 当终止错误；docker 的 mysql 密码警告需忽略
$PSNativeCommandUseErrorActionPreference = $false
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "===== 1. 定时任务 TalentMindCollect =====" -ForegroundColor Cyan
$task = schtasks /Query /TN "TalentMindCollect" /V /FO LIST 2>$null
if ($task) {
    $task | Select-String -Pattern "Status|Last Run Time|Last Result|Next Run Time" | ForEach-Object { $_.Line.Trim() }
} else {
    Write-Host "（任务未注册：schtasks /Create ... 见 scripts\collect_daily.ps1 注释）"
}

Write-Host "`n===== 2. 最近采集日志 =====" -ForegroundColor Cyan
$LogDir = Join-Path $RepoRoot "data\local\logs"
if (Test-Path $LogDir) {
    $latest = Get-ChildItem $LogDir -Filter "collect_daily-*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        Write-Host "日志文件: $($latest.Name)（$($latest.LastWriteTime)）"
        Get-Content $latest.FullName -Tail 15
    } else {
        Write-Host "（尚无日志文件——每日 02:00 首次运行后生成）"
    }
} else {
    Write-Host "（日志目录不存在：$LogDir）"
}

Write-Host "`n===== 3. 数据库采集量 =====" -ForegroundColor Cyan
$listener = Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    Write-Host "（MySQL 未监听 3306，请先 docker compose up -d）"
    exit 0
}
$oldPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"  # docker stderr（mysql 密码警告）不终止
$rows = docker exec talentmind-mysql-1 mysql -uroot -ptalentmind --default-character-set=utf8mb4 -N -e "SELECT 'jd_pool 总量', COUNT(*) FROM talentmind.jd_pool UNION ALL SELECT '  - linkedin', COUNT(*) FROM talentmind.jd_pool WHERE source='linkedin' UNION ALL SELECT '  - hn', COUNT(*) FROM talentmind.jd_pool WHERE source='hn' UNION ALL SELECT '  - cross_source 命中', COUNT(*) FROM talentmind.jd_pool WHERE cross_source=1 UNION ALL SELECT 'signal 总量', COUNT(*) FROM talentmind.signal UNION ALL SELECT '  - github', COUNT(*) FROM talentmind.signal WHERE source='github' UNION ALL SELECT '  - blog', COUNT(*) FROM talentmind.signal WHERE source='blog' UNION ALL SELECT '最近 JD 采集时间', MAX(crawled_at) FROM talentmind.jd_pool UNION ALL SELECT '最近信号时间', MAX(captured_at) FROM talentmind.signal;" 2>&1
$ErrorActionPreference = $oldPref
$rows | Where-Object { $_ -notmatch "Warning" } | ForEach-Object { Write-Host $_ }