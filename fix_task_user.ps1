# Run ONCE as Administrator — reconfigures WebtopBot to run as the current user
# without highest privileges, so future schtasks /end and /run don't need UAC.

$taskName  = "WebtopBot"
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
$botDir    = $PSScriptRoot

Write-Host "Removing old task..." -ForegroundColor Yellow
schtasks /end /tn $taskName 2>&1 | Out-Null
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Host "Registering new task (runs as $env:USERNAME, no elevation needed)..." -ForegroundColor Yellow

$action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "`"$botDir\start_bot_hidden.vbs`"" `
    -WorkingDirectory $botDir

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -DisallowDemandStart:$false

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Webtop Telegram Bot - auto start (user, no elevation)" `
    -Force | Out-Null

Write-Host "Starting bot..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3
Write-Host "Status: $((Get-ScheduledTask -TaskName $taskName).State)" -ForegroundColor Cyan
Write-Host "Done!" -ForegroundColor Green
