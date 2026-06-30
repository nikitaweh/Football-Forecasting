# run_dashboard.ps1 - one-click launcher for the ORAKEL performance dashboard.
#   1. locates Rscript, 2. ensures CRAN packages, 3. refreshes the data,
#   4. starts the Shiny app and opens it in the browser.
#
# Usage:  right-click > "Run with PowerShell"  (or)  pwsh dashboard\run_dashboard.ps1

$ErrorActionPreference = "Stop"
$DashboardDir = $PSScriptRoot
$RepoRoot = Split-Path $DashboardDir -Parent
$Port = 4849

# Persist R packages in a writable user library.
$env:R_LIBS_USER = Join-Path $env:LOCALAPPDATA "R\win-library\4.6"

# Locate Rscript (winget installs R under Program Files or Program Files (x86)).
$rscript = Get-ChildItem -Path "C:\Program Files\R", "C:\Program Files (x86)\R" `
    -Recurse -Filter "Rscript.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\bin\\x64\\" } | Select-Object -First 1
if (-not $rscript) {
    $rscript = Get-ChildItem -Path "C:\Program Files\R", "C:\Program Files (x86)\R" `
        -Recurse -Filter "Rscript.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $rscript) { Write-Error "Rscript.exe not found. Install R (winget install RProject.R)."; exit 1 }
Write-Host "Using R: $($rscript.FullName)"

# 1) ensure packages (fast no-op once installed)
& $rscript.FullName (Join-Path $DashboardDir "install_packages.R")

# 2) refresh data once up-front (the app also auto-refreshes while running)
$py = Join-Path $RepoRoot "Supportdateien\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py (Join-Path $RepoRoot "Sports Api Data\Testruns\Code\build_dashboard_data.py")

# 3) launch the app (working dir = repo root so runApp('dashboard') resolves)
Set-Location $RepoRoot
Write-Host "Starting dashboard on http://127.0.0.1:$Port ..."
& $rscript.FullName -e "shiny::runApp('dashboard', port = $Port, host = '127.0.0.1', launch.browser = TRUE)"
