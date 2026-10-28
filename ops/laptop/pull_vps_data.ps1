# pull_vps_data.ps1  --  one-way data sync VPS -> laptop (the VPS collects and predicts live,
# the laptop runs backtests and model experiments on a copy of that data).
#
# Downloads the data files the VPS changed since the last pull (see ops/bin/export_data.sh) and
# unpacks them over the repo. Never touches code, Testruns/Datacollection reference or backtest.
# Run by the Windows task "ORAKEL VPS Data Pull" (register_pull_task.ps1), or by hand:
#   powershell -ExecutionPolicy Bypass -File ops\laptop\pull_vps_data.ps1 [-Force] [-All]
# Deletions on the VPS are not mirrored. Laptop runs in future mode write the same files as
# the VPS (Datacollection future) and are overwritten by the next pull.
param(
    [switch]$Force,        # pull even while a backtest / pipeline run is active
    [switch]$All,          # include the raw */Unfiltered/* API dumps (large)
    [long]$Since = -1      # override the stored epoch of the last pull
)
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Vps = if ($env:ORAKEL_VPS) { $env:ORAKEL_VPS } else { '187.126.5.8' }
$Key = if ($env:ORAKEL_PULL_KEY) { $env:ORAKEL_PULL_KEY } else { Join-Path $HOME '.ssh\orakel_pull' }
$StateDir = Join-Path $Root 'logs\vps_pull'   # gitignored
$StateFile = Join-Path $StateDir 'last_pull_epoch.txt'
$LogFile = Join-Path $StateDir 'pull.log'
New-Item -ItemType Directory -Force $StateDir | Out-Null

function Log([string]$msg) {
    $line = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Output $line
}
# The scheduled run has no console: every unexpected error must reach the log.
trap { Log "error: $_ (line $($_.InvocationInfo.ScriptLineNumber))"; exit 1 }

# New data in the middle of a backtest would change its inputs between matchdays: skip, the
# next scheduled pull catches up.
if (-not $Force) {
    $busy = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match 'AI_match_stats_prediction|backtest_matchdays|AI_international' }
    if ($busy) { Log "skipped: model run active (pid $($busy.ProcessId -join ','))"; exit 0 }
}

if ($Since -lt 0) {
    if (-not (Test-Path $StateFile)) { Log "no $StateFile -- run once with -Since <epoch>"; exit 1 }
    $Since = [long](Get-Content $StateFile -Raw).Trim()
}

$archive = Join-Path $StateDir 'pull.tgz'
Remove-Item $archive -ErrorAction SilentlyContinue
# The pull key is bound to export_data.sh on the VPS; the "command" is only the epoch.
# PowerShell 5.1 pipes native stdout as text, which corrupts binary data: let cmd write the file.
$request = if ($All) { "$Since all" } else { "$Since" }
cmd /c "`"$env:WINDIR\System32\OpenSSH\ssh.exe`" -i `"$Key`" -o BatchMode=yes -o ConnectTimeout=30 orakel@$Vps `"$request`" > `"$archive`""
if ($LASTEXITCODE -ne 0) { Log "download failed (ssh exit $LASTEXITCODE)"; exit 1 }

$tar = "$env:WINDIR\System32\tar.exe"
$files = & $tar -tzf $archive
if ($LASTEXITCODE -ne 0) { Log 'archive unreadable -- nothing unpacked'; exit 1 }
$stamp = (& $tar -xzOf $archive .orakel_pull_stamp).Trim()

& $tar -xzf $archive -C $Root --exclude .orakel_pull_stamp
if ($LASTEXITCODE -ne 0) { Log 'unpack failed (file open in another program?) -- retried next pull'; exit 1 }

Set-Content -Path $StateFile -Value $stamp -Encoding ascii
$n = @($files | Where-Object { $_ -ne '.orakel_pull_stamp' }).Count
Log "pulled $n files changed since $Since (VPS stamp $stamp)"
Remove-Item $archive
