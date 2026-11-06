<#
.SYNOPSIS
  No-cost end-to-end smoke test: existing sample recording -> Claude edit -> review -> ready output.

.DESCRIPTION
  This is a workflow validation, not a publishable Short. It bypasses the normal script approval gate
  with --no-script because the owner explicitly approved this test. Paid b-roll is disabled.
#>
param(
  [string]$Recording = "",
  [string]$Layout = "corner"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:BROLL_PROVIDER = "none"
$env:Path = "$Root\.venv\Scripts;$env:Path"

New-Item -ItemType Directory -Force -Path ".state", "ready" | Out-Null

if (-not $Recording) {
  $sample = Get-ChildItem "inbox\samples" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -match '^\.(mp4|mov|mkv|m4v|webm)$' } |
    Select-Object -First 1
  if (-not $sample) {
    throw "No sample recording found in inbox\samples."
  }
  $Recording = $sample.FullName
}

$before = Get-Date
$log = ".state\e2e-test-$(Get-Date -Format yyyyMMdd-HHmmss).log"
$prompt = @"
/edit "$Recording" --no-script --layout $Layout

This is the owner's explicitly approved end-to-end workflow TEST.
- Do not ask for script approval.
- Do not use paid APIs. BROLL_PROVIDER=none is intentional; use presenter-only fallback.
- Complete transcription, human edit decisions, compose, thumbnail, review, fix loop, and ready metadata.
- Record each blocker and its resolution in the final report.
"@

$prompt | claude --model opus -p --permission-mode acceptEdits `
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Agent" 2>&1 |
  Tee-Object -FilePath $log

$output = Get-ChildItem "ready" -Filter "*.mp4" |
  Where-Object { $_.LastWriteTime -ge $before } |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $output) {
  throw "End-to-end test produced no ready MP4. See $log"
}

Write-Host "READY: $($output.FullName)" -ForegroundColor Green
Write-Host "LOG:   $((Resolve-Path $log).Path)"
