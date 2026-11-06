<#  Weekly Community post draft -> community\<date>.md (headless Claude Code). Scheduled by setup\register-daily-task.ps1. #>
param([string]$Focus = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:Path = "$Root\.venv\Scripts;$env:Path"
New-Item -ItemType Directory -Force -Path "community", ".state" | Out-Null
$log = ".state\community-$(Get-Date -Format yyyyMMdd).log"
claude -p "/analytics" --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,Agent" 2>&1 | Tee-Object -FilePath $log
claude -p "/community $Focus" --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,Agent" 2>&1 | Tee-Object -FilePath $log
$f = Get-ChildItem community -Filter "*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($f) { Start-Process $f.FullName }
