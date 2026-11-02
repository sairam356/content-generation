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

Write-Host "`n[3/6] Claude Code + Higgsfield CLI (npm)" -ForegroundColor Yellow
if (Need "claude")     { npm install -g @anthropic-ai/claude-code }
if (Need "higgsfield") { npm install -g @higgsfield/cli }
RefreshPath

Write-Host "`n[4/6] Higgsfield MCP server for Claude Code (user scope) + skills" -ForegroundColor Yellow
try { claude mcp add --transport http --scope user higgsfield https://mcp.higgsfield.ai/mcp 2>$null | Out-Null } catch { }
try { npx -y skills add higgsfield-ai/skills -y 2>$null | Out-Null } catch { Write-Host "  (skills install skipped - optional)" }

Write-Host "`n[5/6] Config" -ForegroundColor Yellow
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "  created .env - fill GEMINI_API_KEY and ELEVENLABS_API_KEY" }
New-Item -ItemType Directory -Force -Path "assets\me\photos","assets\me\voice","projects",".state" | Out-Null

Write-Host "`n[6/6] Done. Next steps:" -ForegroundColor Green
Write-Host @"
  1. notepad .env                    -> paste GEMINI_API_KEY and ELEVENLABS_API_KEY
  2. higgsfield auth login           -> sign in (paid Higgsfield plan required)
  3. claude                          -> first run: log in; then type /mcp and authenticate 'higgsfield' (optional, CLI is enough)
  4. Copy 5-20 photos of you  -> assets\me\photos\     (varied angles, good light, one full-body)
     Copy 1-3 voice recordings -> assets\me\voice\      (1-3 min total, quiet room, speaking Telugu)
  5. .\.venv\Scripts\python -m pipeline voice clone     -> clones your voice (ElevenLabs)
     .\.venv\Scripts\python -m pipeline voice preview   -> listen to .state\preview.wav
  6. .\run.ps1 -Url https://www.youtube.com/shorts/XXXXXXXXXXX
"@
