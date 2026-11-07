<#
.SYNOPSIS  Drop a recording into inbox\ -> Claude Code edits it -> ready\<name>.mp4 (+ .jpg, .md).
           Keep this window open (or register it at logon with setup\register-daily-task.ps1 -Watcher).
.EXAMPLE   .\watch-inbox.ps1                 # default layout from memory\style.md
           .\watch-inbox.ps1 -Layout circle-top
#>
param([string]$Layout = "", [string]$Script = "", [int]$PollSec = 15)
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
    # space-free file name: Windows PowerShell 5.1 does not escape embedded quotes for native exes, so a path with
    # spaces split the -p prompt (e.g. "WhatsApp Video ... .mp4" arrived as "/edit ...\WhatsApp" and the
    # -Script/-Layout arguments were lost). Keep every token in the prompt free of spaces and quotes.
    $rec = "$job\$name$($f.Extension.ToLower())"
    Move-Item $f.FullName $rec
    $log = "$job\claude.log"
    Write-Host "`n== $(Get-Date -Format HH:mm) editing $($f.Name) -> $rec" -ForegroundColor Yellow
    $args = "/edit $rec"
    if ($Script) { $args += " $Script" }
    if ($Layout) { $args += " --layout $Layout" }
    claude --model opus -p $args --permission-mode acceptEdits --allowedTools "Bash,Read,Write,Edit,Glob,Grep,Agent,WebSearch,WebFetch,mcp__claude_ai_Canva,mcp__claude_ai_Google_Drive,mcp__claude-in-chrome,mcp__plugin_playwright_playwright" 2>&1 | Tee-Object -FilePath $log
    $out = Get-ChildItem ready -Filter "*.mp4" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $verified = $false
    if ($out -and $out.LastWriteTime -gt (Get-Date).AddMinutes(-90)) {
      python -m pipeline verify $out.FullName | Out-File -Append -FilePath $log -Encoding utf8
      $verified = ($LASTEXITCODE -eq 0)
    }
    if ($verified) {
      Write-Host "READY (verified, full decode ok): $($out.FullName)" -ForegroundColor Green
      try { [System.Media.SystemSounds]::Asterisk.Play() } catch {}
    } else {
      Write-Host "No verified output produced - see $log" -ForegroundColor Red
    }
  }
  Start-Sleep $PollSec
}
