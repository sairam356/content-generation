<#
.SYNOPSIS
  No-cost end-to-end smoke test: existing sample recording -> Claude edit -> review -> ready output.

.DESCRIPTION
  This is a workflow validation, not a publishable Short. It bypasses the normal script approval gate
  with --no-script because the owner explicitly approved this test. Paid b-roll is disabled.
#>
param(
  [string]$Recording = "",
  [string]$Layout = "corner",
  [int]$Count = 2
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:BROLL_PROVIDER = "none"
$env:WHISPER_MODEL = "tiny"
$env:Path = "$Root\.venv\Scripts;$env:Path"

New-Item -ItemType Directory -Force -Path ".state", "ready" | Out-Null

if ($Recording) {
  $recordings = @($Recording)
} else {
  $recordings = @(Get-ChildItem "inbox\samples" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -match '^\.(mp4|mov|mkv|m4v|webm)$' } |
    Select-Object -First $Count | ForEach-Object { $_.FullName })
  if (-not $recordings) {
    throw "No sample recording found in inbox\samples."
  }
}

$results = @()
foreach ($Recording in $recordings) {
$before = Get-Date
$log = ".state\e2e-test-$(Get-Date -Format yyyyMMdd-HHmmss).log"
# The prompt MUST start with "/edit" at column 1, otherwise Claude Code does not treat it as a skill call.
$prompt = @"
/edit "$Recording" --no-script --layout $Layout

This is the owner's explicitly approved end-to-end workflow TEST.
- Do not ask for script approval.
- Do not use paid APIs. BROLL_PROVIDER=none is intentional; use presenter-only fallback.
- Complete transcription, human edit decisions, compose, thumbnail, review, fix loop, and ready metadata.
- Record each blocker and its resolution in the final report.
- The video counts as done only when `python -m pipeline verify <ready mp4>` reports ok.
"@

$prompt | claude --model opus -p --permission-mode acceptEdits `
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Agent" 2>&1 |
  ForEach-Object { Write-Host $_; Add-Content -Path $log -Value "$_" -Encoding UTF8 }

$output = Get-ChildItem "ready" -Filter "*.mp4" |
  Where-Object { $_.LastWriteTime -ge $before } |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $output) {
  Write-Host "FAIL: no ready MP4 for $Recording. See $log" -ForegroundColor Red
  $results += "FAIL (no output)  $Recording  log=$log"
  continue
}

python -m pipeline verify $output.FullName | Out-File -Append -FilePath $log -Encoding utf8
if ($LASTEXITCODE -ne 0) {
  Write-Host "FAIL: $($output.FullName) failed verification (incomplete/unplayable). See $log" -ForegroundColor Red
  $results += "FAIL (verify)  $($output.FullName)  log=$log"
  continue
}

Write-Host "READY (verified): $($output.FullName)" -ForegroundColor Green
$results += "OK  $($output.FullName)  log=$log"
}

Write-Host ""
Write-Host "=== SMOKE TEST SUMMARY ($($results.Count) recordings) ==="
$results | ForEach-Object { Write-Host $_ }
$results | Out-File -FilePath ".state\e2e-summary.txt" -Encoding utf8
if ($results -match '^FAIL') { exit 1 }
