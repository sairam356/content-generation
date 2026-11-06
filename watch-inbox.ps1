<#
.SYNOPSIS  Drop a recording into inbox\ -> Claude Code edits it -> ready\<name>.mp4 (+ .jpg, .md).
           Keep this window open (or register it at logon with setup\register-daily-task.ps1 -Watcher).
.EXAMPLE   .\watch-inbox.ps1                 # default layout from memory\style.md
           .\watch-inbox.ps1 -Layout circle-top
#>
param([string]$Layout = "", [int]$PollSec = 15)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:Path = "$Root\.venv\Scripts;$env:Path"
New-Item -ItemType Directory -Force -Path "inbox", "ready", "inbox\done", ".state" | Out-Null
Write-Host "Watching $Root\inbox for new recordings (mp4/mov/mkv). Ctrl+C to stop." -ForegroundColor Green
while ($true) {
  $files = Get-ChildItem inbox -File | Where-Object { $_.Extension -match '^\.(mp4|mov|mkv|m4v|webm)$' }
  foreach ($f in $files) {
    # wait until the file stopped growing (copy finished)
    $s1 = $f.Length; Start-Sleep 5; $s2 = (Get-Item $f.FullName).Length
    if ($s1 -ne $s2) { continue }
    $stamp = Get-Date -Format yyyyMMdd-HHmmss
    $name = ($f.BaseName -replace '[^\w-]+', '-')
    $job = "inbox\$stamp-$name"
    New-Item -ItemType Directory -Force -Path $job | Out-Null
    Move-Item $f.FullName "$job\$($f.Name)"
    $log = "$job\claude.log"
    Write-Host "`n== $(Get-Date -Format HH:mm) editing $($f.Name) -> $job" -ForegroundColor Yellow
    $args = "/edit $job\$($f.Name)"
    if ($Layout) { $args += " --layout $Layout" }
    claude --model opus -p $args --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Agent" 2>&1 | Tee-Object -FilePath $log
    $out = Get-ChildItem ready -Filter "*.mp4" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($out -and $out.LastWriteTime -gt (Get-Date).AddMinutes(-90)) {
      Write-Host "READY: $($out.FullName)" -ForegroundColor Green
      try { [System.Media.SystemSounds]::Asterisk.Play() } catch {}
    } else {
      Write-Host "No output produced - see $log" -ForegroundColor Red
    }
  }
  Start-Sleep $PollSec
}
