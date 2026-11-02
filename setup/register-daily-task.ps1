<#
.SYNOPSIS
  Registers a Windows Task Scheduler job that briefs the newest Shorts from channels.txt every morning
  (Gemini analysis + Telugu script only - no paid video generation). Review projects\ and run
  .\run.ps1 -Project <folder> -SkipAnalyze for the ones you want to produce.
.EXAMPLE
  .\setup\register-daily-task.ps1 -At 07:30
  .\setup\register-daily-task.ps1 -Remove
#>
param([string]$At = "07:30", [switch]$Remove)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Name = "TeluguShorts-DailyBriefs"
if ($Remove) { Unregister-ScheduledTask -TaskName $Name -Confirm:$false; Write-Host "removed $Name"; exit }
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$Action = New-ScheduledTaskAction -Execute $Py -Argument "-m pipeline daily" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Registered '$Name' daily at $At. Logs: run 'python -m pipeline daily' manually to see output."
