# Install / refresh the Windows Task Scheduler job for Research Intelligence Engine.
# Morning 6:30 AM every day (local time). Evening briefs are not scheduled.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Bat = Join-Path $PSScriptRoot "run_scheduled.bat"

if (-not (Test-Path $Bat)) {
    throw "Missing runner: $Bat"
}

function Register-RieTask {
    param(
        [string]$Name,
        [string]$BriefType,
        [string]$Time
    )
    $action = New-ScheduledTaskAction -Execute $Bat -Argument $BriefType -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew
    # A missed 6:30 run must not fire the moment the PC wakes in the afternoon.
    $settings.StartWhenAvailable = $false
    Register-ScheduledTask `
        -TaskName $Name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Research Intelligence Engine $BriefType brief" `
        -Force | Out-Null
    Write-Host "Registered: $Name at $Time ($BriefType)"
}

$EveningTask = "ResearchIntel Evening Brief"
if (Get-ScheduledTask -TaskName $EveningTask -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $EveningTask -Confirm:$false
    Write-Host "Removed: $EveningTask"
}

Register-RieTask -Name "ResearchIntel Morning Brief" -BriefType "morning" -Time "6:30AM"

Write-Host ""
Write-Host "Done. The morning brief runs at 6:30 AM only when this Windows user is logged in."
Write-Host "If the PC is asleep at 6:30, that day's brief is skipped (it will not send later)."
Write-Host "A run that still starts at or after 9:00 AM local is also skipped."
Write-Host "Make sure EMAIL_APP_PASSWORD is set in .env before the first scheduled send."
Write-Host "Test manually:"
Write-Host "  $Bat morning"
