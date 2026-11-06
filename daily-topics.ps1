<#
.SYNOPSIS  Daily topic board: 10 ideas with full Telugu scripts in topics\<date>\ (headless Claude Code).
           Scheduled by setup\register-daily-task.ps1; run by hand any time.
#>
param([int]$Count = 10, [string]$Focus = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:Path = "$Root\.venv\Scripts;$env:Path"
New-Item -ItemType Directory -Force -Path "topics", ".state" | Out-Null
$log = ".state\daily-$(Get-Date -Format yyyyMMdd).log"
"== $(Get-Date) /topics $Count $Focus" | Tee-Object -FilePath $log -Append
claude --model opus -p "/topics $Count $Focus" --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Agent" 2>&1 | Tee-Object -FilePath $log -Append
$today = Get-Date -Format yyyy-MM-dd
if (Test-Path "topics\$today\README.md") { Start-Process "topics\$today\README.md" }
