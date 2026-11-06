<#
.SYNOPSIS
  One-command first render using a WhatsApp video placed in the repository root.
  Clones your voice if ElevenLabs allows it; otherwise falls back to a stock Telugu voice.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run-first-local.ps1
  powershell -ExecutionPolicy Bypass -File .\run-first-local.ps1 -VoiceId <elevenlabs voice id>
#>
param(
  [string]$Project = "projects\meal-maker",
  [string]$Video,
  [string]$VoiceId,
  [string]$FallbackVoiceId = "ge94MQm6fYaUCnxz1us6",  # "Srinu" - stock Telugu male voice
  [switch]$Reanalyze                                   # redo the Gemini analysis/script and every clip
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
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
& ffmpeg -y -loglevel error -i $Video -vn -ac 1 -ar 44100 "assets\me\voice\sample.wav"
if ($LASTEXITCODE -ne 0) { throw "Could not extract audio from $Video" }

if (-not $VoiceId -and (Test-Path ".env")) {
  $voiceLine = Get-Content ".env" | Where-Object { $_ -match "^ELEVENLABS_VOICE_ID=.+" } | Select-Object -Last 1
  if ($voiceLine) { $VoiceId = ($voiceLine -split "=", 2)[1].Trim() }
}
if (-not $VoiceId) {
  Write-Host "`n== Cloning your voice in ElevenLabs ==" -ForegroundColor Yellow
  & $Py -m pipeline voice clone
  if ($LASTEXITCODE -eq 0) {
    $voiceLine = Get-Content ".env" | Where-Object { $_ -match "^ELEVENLABS_VOICE_ID=.+" } | Select-Object -Last 1
    if ($voiceLine) { $VoiceId = ($voiceLine -split "=", 2)[1].Trim() }
  } else {
    Write-Host "Voice cloning not allowed on this ElevenLabs plan/key - using stock Telugu voice $FallbackVoiceId for now." -ForegroundColor Yellow
    Write-Host "To use YOUR voice later: upgrade to Starter+, create an API key with 'Voices: Write', then run  python -m pipeline voice clone" -ForegroundColor Yellow
    $VoiceId = $FallbackVoiceId
  }
}

Write-Host "`n== ElevenLabs: Telugu narration (voice $VoiceId) ==" -ForegroundColor Yellow
if ($Reanalyze) {
  $Url = (Get-Content (Join-Path $Project "brief.json") -Raw -Encoding UTF8 | ConvertFrom-Json).source_url
  $ProjName = Split-Path -Leaf $Project
  foreach ($d in "audio", "frames", "clips", "build") { Remove-Item -Recurse -Force (Join-Path $Project $d) -ErrorAction SilentlyContinue }
  Remove-Item -Force (Join-Path $Project "timeline.json"), (Join-Path $Project "final.mp4") -ErrorAction SilentlyContinue
  & $Py -m pipeline analyze $Url --name $ProjName
  if ($LASTEXITCODE -ne 0) { throw "analyze failed" }
}
& $Py -m pipeline tts $Project --voice-id $VoiceId
if ($LASTEXITCODE -ne 0) { throw "TTS failed" }

Write-Host "`n== Local renderer: Wav2Lip + Gemini images -> assembly ==" -ForegroundColor Yellow
& ".\run.ps1" -Project $Project -SkipAnalyze -SkipVoice -Renderer local
if ($LASTEXITCODE -ne 0) { throw "First local render failed" }

$Final = Join-Path $Project "final.mp4"
if (-not (Test-Path $Final)) { throw "Render finished without $Final" }
& ffprobe -v error -show_entries stream=codec_type,width,height -show_entries format=duration -of default=nw=1 $Final
Write-Host "`nDone: $Final" -ForegroundColor Green
