# Run this script ONCE as Administrator to set up auto-start
# Right-click PowerShell → "Run as Administrator" → paste this script path

$botDir = $PSScriptRoot
$vbsPath = "$botDir\start_bot_hidden.vbs"
$logsDir = "$botDir\logs"

# Create logs folder
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
    Write-Host "Created logs folder: $logsDir"
}

# Register Task Scheduler job
$taskName = "WebtopBot"

# Remove old task if exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "`"$vbsPath`""

# Trigger: at logon of current user
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Settings: restart on failure, run even on battery
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host ""
Write-Host "✅ Task '$taskName' registered successfully!"
Write-Host "   Bot will start automatically when you log in to Windows."
Write-Host ""
Write-Host "To start it NOW (without logging out):"
Write-Host "   Start-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "To stop it:"
Write-Host "   Stop-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "To view logs:"
Write-Host "   Get-Content '$logsDir\bot.log' -Tail 50"
