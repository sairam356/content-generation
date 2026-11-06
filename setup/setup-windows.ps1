<#
.SYNOPSIS
  One-time setup for the Telugu Shorts pipeline on Windows 10/11.
  Run from PowerShell (not as Administrator; winget installs per-user):
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
    .\setup\setup-windows.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Need($cmd) { -not (Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget($id) {
  Write-Host "  installing $id ..." -ForegroundColor Cyan
  winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
}
function RefreshPath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "`n[1/6] System tools (winget)" -ForegroundColor Yellow
if (Need "winget") { throw "winget is missing. Install 'App Installer' from the Microsoft Store, then re-run." }
if (Need "git")    { Winget "Git.Git" }
if (Need "python") { Winget "Python.Python.3.12" }
if (Need "node")   { Winget "OpenJS.NodeJS.LTS" }
if (Need "ffmpeg") { Winget "Gyan.FFmpeg" }
RefreshPath
foreach ($c in "git","python","node","npm","ffmpeg","ffprobe") {
  if (Need $c) { throw "$c still not on PATH. Close this window, open a new PowerShell, and re-run the script." }
}

Write-Host "`n[2/6] Python packages" -ForegroundColor Yellow
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt -q

Write-Host "`n[3/6] Claude Code (npm)" -ForegroundColor Yellow
if (Need "claude") { npm install -g @anthropic-ai/claude-code }
RefreshPath

Write-Host "`n[4/6] Whisper model (first transcription downloads ~500 MB; pre-fetching now)" -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('  whisper small ready')"

Write-Host "`n[5/6] Config" -ForegroundColor Yellow
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "  created .env - fill ELEVENLABS_API_KEY (backgrounds) and GEMINI_API_KEY (/ref)" }
New-Item -ItemType Directory -Force -Path "inbox","ready","topics","memory","projects",".state","assets\music" | Out-Null

Write-Host "`n[6/6] Done. Next steps:" -ForegroundColor Green
Write-Host @"
  1. notepad .env            -> ELEVENLABS_API_KEY (AI backgrounds), GEMINI_API_KEY (optional, /ref)
  2. notepad channels.txt    -> your 10+ inspiration channels, one URL per line
  3. claude                  -> log in once; install the 'Claude in Chrome' extension (used for /music and Canva); try /ref <url>, /topics
  4. .\setup\register-daily-task.ps1 -At 07:30 -Watcher   -> daily topics + inbox auto-edit at logon
  5. Record with topics\<date>\<nn>\teleprompter.html open, drop the video into inbox\ -> ready\<name>.mp4
"@
