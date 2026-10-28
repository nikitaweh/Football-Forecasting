# register_pull_task.ps1  --  creates the Windows task "ORAKEL VPS Data Pull": daily at 07:00
# (after the VPS postmatch 03:30 and collect-daily 05:15 jobs) and at logon; a run missed while
# the laptop was off or asleep starts as soon as it is available. Runs as the current user,
# only while logged on, so no password is stored.
#   powershell -ExecutionPolicy Bypass -File ops\laptop\register_pull_task.ps1
$script = Join-Path $PSScriptRoot 'pull_vps_data.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$daily = New-ScheduledTaskTrigger -Daily -At 07:00
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logon.Delay = 'PT5M'
# Battery flags: the Windows default queues the task until the laptop is on mains power.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'ORAKEL VPS Data Pull' -Action $action -Trigger $daily, $logon `
    -Settings $settings -Description 'One-way data sync VPS -> laptop (ops/laptop/pull_vps_data.ps1)' -Force
