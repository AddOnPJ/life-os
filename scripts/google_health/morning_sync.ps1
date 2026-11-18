# 毎朝 6:30（Windows タスクスケジューラ）: Google Health 取得 → 日次ログ反映 → 募集掲載の確認 → push
# ログは secure 配下に出す（コミットされない）。
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
$env:PYTHONIOENCODING = "utf-8"
$log = "secure\health\morning_sync.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

function Invoke-Step([string]$What, [scriptblock]$Cmd) {
    Write-Host "== $What"
    & $Cmd
    if ($LASTEXITCODE -ne 0) { throw "$What が失敗しました (exit $LASTEXITCODE)" }
}

Start-Transcript -Path $log -Append | Out-Null
try {
    Write-Host ("開始 " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    # 先に取り込む（スマホ・クラウドの記録とぶつからないように）
    Invoke-Step "git pull --rebase" { git pull --rebase --autostash }
    Invoke-Step "sync.py fetch" { python scripts/google_health/sync.py fetch --days 2 }
    Invoke-Step "summarize.py" { python scripts/google_health/summarize.py --days 3 }
    # 募集掲載の確認（失敗しても健康データの反映は止めない）
    python scripts/listing_check.py
    if ($LASTEXITCODE -ne 0) { Write-Host "listing_check.py が失敗（続行）" }

    git add logs/daily
    $today = Get-Date -Format "yyyy-MM-dd"
    foreach ($f in @("domains/addon/agent/obs/listings.json", "domains/addon/agent/obs/listings-$today.json")) {
        if (Test-Path $f) { git add -- $f }
    }
    $extra = git diff --cached --name-only | Where-Object { $_ -notlike "logs/daily/*" -and $_ -notlike "domains/addon/agent/obs/listings*.json" }
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
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
