<#
.SYNOPSIS  Telugu Shorts Studio - local web UI (Scout -> Topics -> Record -> Run -> Ready) at http://localhost:8787
.EXAMPLE   .\studio.ps1              # opens the browser; keep this window open
           .\studio.ps1 -Port 8800
           .\studio.ps1 -Fake        # no credits: a stub claude plays back a fake /edit run (UI test)
#>
param([int]$Port = 8787, [switch]$Fake, [switch]$NoBrowser)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:Path = "$Root\.venv\Scripts;$env:Path"
$env:STUDIO_PORT = "$Port"
if ($Fake) { $env:STUDIO_CLAUDE = "studio\dev\fake_claude.py"; $env:FAKE_SPEED = "0.5" }
python -c "import fastapi, uvicorn, multipart" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Installing studio dependencies ..." -ForegroundColor Yellow; pip install -q -r requirements.txt }
if (-not $NoBrowser) { Start-Job -ScriptBlock { Start-Sleep 2; Start-Process "http://localhost:$using:Port" } | Out-Null }
Write-Host "Telugu Shorts Studio -> http://localhost:$Port  (Ctrl+C to stop)" -ForegroundColor Green
python -m studio
