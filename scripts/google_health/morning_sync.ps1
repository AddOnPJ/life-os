# 毎朝 6:10（Windows タスクスケジューラ。初回の実行で 6:30 から自動で変更）: Google Health 取得 → 日次ログ反映 → 募集掲載の確認 → push
# ログは secure 配下に出す（コミットされない）。
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
$env:PYTHONIOENCODING = "utf-8"
$log = "secure\health\morning_sync.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

$script:step = "開始"
function Invoke-Step([string]$What, [scriptblock]$Cmd) {
    $script:step = $What
    Write-Host "== $What"
    & $Cmd
    if ($LASTEXITCODE -ne 0) { throw "$What が失敗しました (exit $LASTEXITCODE)" }
}

Start-Transcript -Path $log -Append | Out-Null
try {
    Write-Host ("開始 " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    # 先に取り込む（スマホ・クラウドの記録とぶつからないように）
    Invoke-Step "git pull --rebase" { git pull --rebase --autostash }

    # このタスク自身の実行時刻を 6:10 にそろえる（6:23 の AddOn エージェントより前に終わらせるため）
    $taskName = "life-os-google-health"
    $wantAt = "06:10"
    $reschedule = "変更なし"
    try {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
        $cur = ([datetime]$task.Triggers[0].StartBoundary).ToString("HH:mm")
        if ($cur -ne $wantAt) {
            Set-ScheduledTask -TaskName $taskName -Trigger (New-ScheduledTaskTrigger -Daily -At $wantAt) -ErrorAction Stop | Out-Null
            $reschedule = "$cur から $wantAt に変更"
        }
    } catch { $reschedule = "変更できず: " + $_.Exception.Message }
    Write-Host "実行時刻: $reschedule"
    Invoke-Step "sync.py fetch" { python scripts/google_health/sync.py fetch --days 2 }
    Invoke-Step "summarize.py" { python scripts/google_health/summarize.py --days 3 }
    # 募集掲載の確認（失敗しても健康データの反映は止めない）
    python scripts/listing_check.py
    $listingOk = ($LASTEXITCODE -eq 0)
    if (-not $listingOk) { Write-Host "listing_check.py が失敗（続行）" }
    # YouTube の数字（.env に YOUTUBE_API_KEY があるときだけ。失敗しても続行）
    python scripts/youtube_stats.py
    $youtubeOk = ($LASTEXITCODE -eq 0)
    # 詳しい健康とお金の画面（secure/dashboard.html）。PC の中だけ。失敗しても続行
    python scripts/secure_weekly.py

    # PC の同期が動いたことをクラウドに知らせる（secure の中身は書かない）
    $state = [ordered]@{
        ran_at = (Get-Date -Format "yyyy-MM-dd HH:mm")
        ok = $true
        health = "ok"
        listing = $(if ($listingOk) { "ok" } else { "失敗" })
        youtube = $(if ($youtubeOk) { "ok" } else { "失敗" })
        schedule = $reschedule
    }
    New-Item -ItemType Directory -Force "status" | Out-Null
    [IO.File]::WriteAllText((Join-Path (Get-Location) "status\pc-sync.json"), ($state | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))

    git add logs/daily
    $today = Get-Date -Format "yyyy-MM-dd"
    foreach ($f in @("domains/addon/agent/obs/listings.json", "domains/addon/agent/obs/listings-$today.json", "domains/addon/agent/obs/youtube.json", "domains/addon/agent/obs/youtube-$today.json", "status/pc-sync.json")) {
        if (Test-Path $f) { git add -- $f }
    }
    $extra = git diff --cached --name-only | Where-Object { $_ -notlike "logs/daily/*" -and $_ -notlike "domains/addon/agent/obs/listings*.json" -and $_ -notlike "domains/addon/agent/obs/youtube*.json" -and $_ -ne "status/pc-sync.json" }
    if ($extra) { throw "決められたファイル以外が含まれています: $extra" }   # secure 混入の最終ガード
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { Write-Host "変更なし。コミットしません。"; return }

    Invoke-Step "git commit" { git commit -m "Google Health の日次反映と募集掲載の確認（自動）" }
    git push
    if ($LASTEXITCODE -ne 0) {
        # 競合で弾かれたとき 1 回だけやり直す
        Invoke-Step "git pull --rebase（再）" { git pull --rebase --autostash }
        Invoke-Step "git push（再）" { git push }
    }
    Write-Host "完了"
} catch {
    Write-Host ("失敗: " + $_)
    # 失敗したことをクラウドに知らせる（どの段階か・エラーの種類だけ。secure の中身やパスは書かない）
    try {
        $msg = ($_.Exception.Message -replace '[A-Za-z]:\\[^\s"]+', '<path>')
        if ($msg.Length -gt 200) { $msg = $msg.Substring(0, 200) }
        $state = [ordered]@{ ran_at = (Get-Date -Format "yyyy-MM-dd HH:mm"); ok = $false; failed_step = $script:step; error = $msg }
        New-Item -ItemType Directory -Force "status" | Out-Null
        [IO.File]::WriteAllText((Join-Path (Get-Location) "status\pc-sync.json"), ($state | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        git reset -q
        git add -- "status/pc-sync.json"
        git commit -q -m "PC の同期が失敗（$($script:step)）"
        git pull -q --rebase --autostash
        git push -q
    } catch { Write-Host ("失敗の報告もできませんでした: " + $_) }
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
