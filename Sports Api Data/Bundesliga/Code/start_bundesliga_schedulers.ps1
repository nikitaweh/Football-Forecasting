$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$defaultPython = Join-Path $projectRoot "Supportdateien\.venv\Scripts\python.exe"
$pythonExe = if (Test-Path $defaultPython) { $defaultPython } else { "python" }

$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = @($machinePath, $userPath) -ne $null -join ";"
Remove-Item Env:PATH -ErrorAction SilentlyContinue

$automationRoot = "C:\Users\wehni\.codex\automations\automate-run\bundesliga_scheduler"
$stateRoot = $automationRoot
$logRoot = Join-Path $stateRoot "logs"
$pidRoot = Join-Path $stateRoot "pids"
$legacyStatePaths = @(
    (Join-Path $projectRoot "Supportdateien\bundesliga_scheduler\state.json"),
    (Join-Path $projectRoot "Supportdateien\BundesligaSchedulerLogs\bundesliga_scheduler_registry.json")
)

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
New-Item -ItemType Directory -Force -Path $pidRoot | Out-Null

$scripts = @(
    @{ Name = "fixtures_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\Fixtures Bundesliga.py" },
    @{ Name = "injuries_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\injuries_78.py" },
    @{ Name = "league_info_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\League General Info.py" },
    @{ Name = "lineups_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\lineups_78.py" },
    @{ Name = "matchstats_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\match_statistics._78.py" },
    @{ Name = "playerstats_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\player individuel statistic_78.py" },
    @{ Name = "teams_unfiltered"; Path = "Sports Api Data\Bundesliga\Unfiltered\Code\Team General Info.py" },
    @{ Name = "future_weather_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\future_weather_hourly_78.py" },
    @{ Name = "historic_weather_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\historic_weather_data_78.py" },
    @{ Name = "injuries_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\injuries_78.py" },
    @{ Name = "lineups_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\line ups_78.py" },
    @{ Name = "matchstats_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\match statistics.py" },
    @{ Name = "playerstats_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\playerstatistics.py" },
    @{ Name = "stammdaten_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\Stammdaten_78.py" },
    @{ Name = "teams_filtered"; Path = "Sports Api Data\Bundesliga\Filtered\Code\teams general info.py" }
)

function Get-PidFilePath([string]$name) {
    return Join-Path $pidRoot "$name.pid"
}

function Get-MetaFilePath([string]$name) {
    return Join-Path $pidRoot "$name.json"
}

function Test-LegacyStateProcess([string]$name) {
    foreach ($legacyPath in $legacyStatePaths) {
        if (-not (Test-Path $legacyPath)) {
            continue
        }

        try {
            $legacyState = Get-Content $legacyPath -Raw | ConvertFrom-Json -AsHashtable
        } catch {
            continue
        }

        if (-not $legacyState.ContainsKey($name)) {
            continue
        }

        $entry = $legacyState[$name]
        if (-not $entry -or -not $entry.ContainsKey("pid")) {
            continue
        }

        $proc = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
        if ($null -eq $proc) {
            continue
        }

        if ($entry.ContainsKey("start_time_utc") -and $entry.start_time_utc) {
            $actualStart = $proc.StartTime.ToUniversalTime().ToString("o")
            if ($actualStart -ne [string]$entry.start_time_utc) {
                continue
            }
        } elseif ($entry.ContainsKey("started_at") -and $entry.started_at) {
            $actualStart = $proc.StartTime.ToString("o")
            if ($actualStart -ne [string]$entry.started_at) {
                continue
            }
        }

        Set-Content -Path (Get-PidFilePath $name) -Value $proc.Id
        $meta = [PSCustomObject]@{
            name = $name
            pid = $proc.Id
            migrated_from = $legacyPath
            started_at = $proc.StartTime.ToUniversalTime().ToString("o")
            detected_at = (Get-Date).ToUniversalTime().ToString("o")
        } | ConvertTo-Json -Depth 3
        Set-Content -Path (Get-MetaFilePath $name) -Value $meta
        return $proc.Id
    }

    return $null
}

function Test-ManagedProcess([string]$name) {
    $pidFile = Get-PidFilePath $name
    if (-not (Test-Path $pidFile)) {
        $legacyPid = Test-LegacyStateProcess $name
        return ($null -ne $legacyPid)
    }

    $rawPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not $rawPid) {
        Remove-Item $pidFile -ErrorAction SilentlyContinue
        return $false
    }

    $proc = Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        Remove-Item $pidFile -ErrorAction SilentlyContinue
        Remove-Item (Get-MetaFilePath $name) -ErrorAction SilentlyContinue
        return $false
    }

    return $true
}

function Start-ManagedScript($script) {
    $scriptPath = Join-Path $projectRoot $script.Path
    if (-not (Test-Path $scriptPath)) {
        throw "Datei nicht gefunden: $scriptPath"
    }

    if (Test-ManagedProcess $script.Name) {
        $runningPid = Get-Content (Get-PidFilePath $script.Name) | Select-Object -First 1
        return [PSCustomObject]@{
            Name = $script.Name
            Status = "already_running"
            Pid = [int]$runningPid
            Script = $scriptPath
        }
    }

    $stdoutLog = Join-Path $logRoot "$($script.Name).stdout.log"
    $stderrLog = Join-Path $logRoot "$($script.Name).stderr.log"

    $escapedPython = $pythonExe.Replace("'", "''")
    $escapedScript = $scriptPath.Replace("'", "''")
    $escapedStdout = $stdoutLog.Replace("'", "''")
    $escapedStderr = $stderrLog.Replace("'", "''")
    $wrapperCommand = "& '$escapedPython' -u '$escapedScript' 1>> '$escapedStdout' 2>> '$escapedStderr'"

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "powershell.exe"
    $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command " + '"' + $wrapperCommand.Replace('"', '\"') + '"'
    $psi.WorkingDirectory = $projectRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::new()
    $proc.StartInfo = $psi
    [void]$proc.Start()

    Set-Content -Path (Get-PidFilePath $script.Name) -Value $proc.Id
    $meta = [PSCustomObject]@{
        name = $script.Name
        pid = $proc.Id
        script = $scriptPath
        started_at = (Get-Date).ToString("s")
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
        python = $pythonExe
    } | ConvertTo-Json -Depth 3
    Set-Content -Path (Get-MetaFilePath $script.Name) -Value $meta

    return [PSCustomObject]@{
        Name = $script.Name
        Status = "started"
        Pid = $proc.Id
        Script = $scriptPath
    }
}

$results = foreach ($script in $scripts) {
    Start-ManagedScript $script
}

$results | Format-Table -AutoSize
