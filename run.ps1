<#
.SYNOPSIS
  Full pipeline for one reference Short:
    Gemini analysis + Telugu script -> ElevenLabs narration (your voice) -> Claude Code + Higgsfield visuals -> final.mp4
.EXAMPLE
  .\run.ps1 -Url https://www.youtube.com/shorts/abc123DEF45
  .\run.ps1 -Project projects\20261102-my-short-abc123DEF45 -SkipAnalyze        # resume an existing project
  .\run.ps1 -Url ... -Headless                                                   # no interactive Claude session
#>
param(
  [string]$Url,
  [string]$Project,
  [switch]$SkipAnalyze,
  [switch]$SkipVoice,
  [switch]$BriefOnly,
  [switch]$Headless,
  [ValidateSet("deep","clean","none")][string]$VoicePreset
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

if (-not $SkipAnalyze) {
  if (-not $Url) { throw "Give -Url <youtube short url> (or -Project with -SkipAnalyze)" }
  Write-Host "`n== 1/3 Gemini: understanding the Short and writing the Telugu script ==" -ForegroundColor Yellow
  $out = & $Py -m pipeline analyze $Url
  if ($LASTEXITCODE -ne 0) { throw "analyze failed" }
  $Project = ($out | Select-Object -Last 1).Trim()
}
if (-not $Project) { throw "No project folder. Pass -Project." }
$Project = (Resolve-Path $Project).Path
$Rel = "projects\" + (Split-Path -Leaf $Project)
Write-Host "Project: $Rel" -ForegroundColor Green
Write-Host "Script:  $Rel\brief.md  (open it, tweak the Telugu if you like, then continue)"

if ($BriefOnly) { exit 0 }

if (-not $SkipVoice) {
  Write-Host "`n== 2/3 ElevenLabs: narration in your cloned voice ==" -ForegroundColor Yellow
  $ttsArgs = @("-m","pipeline","tts",$Project)
  if ($VoicePreset) { $ttsArgs += @("--preset",$VoicePreset) }
  & $Py @ttsArgs
  if ($LASTEXITCODE -ne 0) { throw "tts failed" }
}

Write-Host "`n== 3/3 Claude Code + Higgsfield: visuals, lip-sync, assembly ==" -ForegroundColor Yellow
$prompt = "/make-short $Rel"
if ($Headless) {
  claude -p $prompt --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,mcp__higgsfield__*"
} else {
  claude $prompt
}
if (Test-Path "$Project\final.mp4") { Write-Host "`nDone: $Rel\final.mp4" -ForegroundColor Green }
