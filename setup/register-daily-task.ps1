<#
.SYNOPSIS
  Windows Task Scheduler: every morning run daily-topics.ps1 (10 topics with scripts in topics\<date>\),
  and optionally start watch-inbox.ps1 at logon (auto-edit anything dropped into inbox\).
.EXAMPLE
  .\setup\register-daily-task.ps1 -At 07:30            # daily topics
  .\setup\register-daily-task.ps1 -Watcher             # also start the inbox watcher at logon
  .\setup\register-daily-task.ps1 -Remove
#>
param([string]$At = "07:30", [switch]$Watcher, [switch]$Remove)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$T1 = "TeluguShorts-DailyTopics"; $T2 = "TeluguShorts-InboxWatcher"; $T3 = "TeluguShorts-WeeklyCommunity"
if ($Remove) {
  foreach ($n in $T1, $T2, $T3) { Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue }
  Write-Host "removed"; exit
}
$ps = "powershell.exe"
$a1 = New-ScheduledTaskAction -Execute $ps -Argument "-ExecutionPolicy Bypass -File `"$Root\daily-topics.ps1`"" -WorkingDirectory $Root
$tr1 = New-ScheduledTaskTrigger -Daily -At $At
$st = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $T1 -Action $a1 -Trigger $tr1 -Settings $st -Force | Out-Null
Write-Host "Registered '$T1' daily at $At -> topics\<date>\README.md"
$a3 = New-ScheduledTaskAction -Execute $ps -Argument "-ExecutionPolicy Bypass -File `"$Root\weekly-community.ps1`"" -WorkingDirectory $Root
$tr3 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $At
Register-ScheduledTask -TaskName $T3 -Action $a3 -Trigger $tr3 -Settings $st -Force | Out-Null
Write-Host "Registered '$T3' weekly (Sunday $At) -> community\<date>.md"
if ($Watcher) {
  $a2 = New-ScheduledTaskAction -Execute $ps -Argument "-ExecutionPolicy Bypass -File `"$Root\watch-inbox.ps1`"" -WorkingDirectory $Root
  $tr2 = New-ScheduledTaskTrigger -AtLogOn
  $st2 = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
  Register-ScheduledTask -TaskName $T2 -Action $a2 -Trigger $tr2 -Settings $st2 -Force | Out-Null
  Write-Host "Registered '$T2' at logon -> drop recordings into inbox\"
}
