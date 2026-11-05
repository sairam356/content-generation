<#
.SYNOPSIS
  One-command first render using a WhatsApp video placed in the repository root.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run-first-local.ps1
#>
param(
  [string]$Project = "projects\meal-maker",
  [string]$Video
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

if (-not $Video) {
  $source = Get-ChildItem -LiteralPath $Root -Filter "WhatsApp Video*.mp4" |
    Sort-Object Length -Descending |
    Select-Object -First 1
  if (-not $source) {
    throw "Put a WhatsApp Video*.mp4 in $Root, or pass -Video <path>."
  }
  $Video = $source.FullName
}

$Video = (Resolve-Path $Video).Path
$Project = (Resolve-Path $Project).Path
New-Item -ItemType Directory -Force "assets\me\video", "assets\me\voice" | Out-Null

Write-Host "`n== Preparing your face video and voice sample ==" -ForegroundColor Yellow
Copy-Item $Video "assets\me\video\base.mp4" -Force
& ffmpeg -y -i $Video -vn -ac 1 -ar 44100 "assets\me\voice\sample.wav"
if ($LASTEXITCODE -ne 0) { throw "Could not extract audio from $Video" }

$voiceId = ""
if (Test-Path ".env") {
  $voiceLine = Get-Content ".env" | Where-Object { $_ -match "^ELEVENLABS_VOICE_ID=.+" } | Select-Object -Last 1
  if ($voiceLine) { $voiceId = ($voiceLine -split "=", 2)[1].Trim() }
}
if (-not $voiceId) {
  Write-Host "`n== Cloning your voice in ElevenLabs ==" -ForegroundColor Yellow
  & $Py -m pipeline voice clone
  if ($LASTEXITCODE -ne 0) { throw "ElevenLabs voice clone failed" }
}

Write-Host "`n== Generating and rendering the first Short ==" -ForegroundColor Yellow
& ".\run.ps1" -Project $Project -SkipAnalyze -Renderer local
if ($LASTEXITCODE -ne 0) { throw "First local render failed" }

$Final = Join-Path $Project "final.mp4"
if (-not (Test-Path $Final)) { throw "Render finished without $Final" }
& ffprobe -v error -show_entries stream=codec_type,width,height -show_entries format=duration -of default=nw=1 $Final
Write-Host "`nDone: $Final" -ForegroundColor Green
