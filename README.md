# Telugu Shorts Studio

You read a script and talk to the camera. Claude Code does everything else like a professional team would:
finds topics, writes scripts, edits the video, checks taste and YouTube rules, reviews its own work.

```
channels.txt + web  ──/topics (every morning)──▶  topics\<date>\  10 ideas, each: script + teleprompter
                                                        │  you read 2, say "approved"
                                                        ▼
                                   record on phone/laptop with teleprompter.html
                                                        │  drop the file in inbox\
                                                        ▼
 watch-inbox.ps1 ──/edit──▶ transcribe → cut like an editor → relevant animated background per beat
                            → layout (corner / circle-top / split / full) → Telugu captions → music
                            → review loop with the specialist panel ──▶ ready\<name>.mp4 + .jpg + .md
                                                        │
                                              /publish ──▶ upload pack (settings, titles, time)
```

**Specialist panel** (Claude subagents): designer · taste · end-viewer · comparison · compliance · reach · reviewer.
**Memory**: `memory\style.md`, `references.md` (`/ref <url>`), `learnings.md` (`/retro`), `done.md`.
**Policy**: `policy\youtube.md` — original content, sources, disclosure, licensed music → monetizable channel.

## Setup (once, PowerShell)
```powershell
git clone -b studio https://github.com/sairam356/content-generation C:\Users\<you>\content-generation
cd C:\Users\<you>\content-generation
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup\setup-windows.ps1        # git/python/node/ffmpeg, .venv + deps, Claude Code, Whisper model
notepad .env                      # ELEVENLABS_API_KEY (AI backgrounds), GEMINI_API_KEY (optional, /ref)
notepad channels.txt              # your 10+ inspiration channels
claude                            # log in; install the "Claude in Chrome" extension for /music
.\setup\register-daily-task.ps1 -At 07:30 -Watcher   # daily topics + inbox watcher at logon
```

## Every day
1. Morning: `topics\<date>\README.md` opens → read two `script.md`, reply `approved` in Claude (or set
   `"approved": true` in `script.json`).
2. Open that folder's `teleprompter.html` (SPACE scrolls), record 9:16, good light, look at the lens.
3. Copy the video into `inbox\` → a few minutes later `ready\<name>.mp4` + thumbnail + metadata.
4. `claude` → `/publish ready\<name>.mp4` → upload with the settings it gives.
5. Weekly (Sunday, scheduled): `/analytics` reads your Studio numbers → rules into memory; `/community` drafts the week's post.

Layouts: `corner` (you lower-left over the background — Osm Dhruva look) · `circle-top` (you in a round frame at the
top) · `split` · `full`. Default lives in `memory\style.md`; per video: `/edit <file> --layout circle-top`.

## Tools (what Claude runs)
`python -m pipeline channels | watch <url> | inspect <url> | teleprompter <script.json> | transcribe <video> | compose <plan.json> | review <video>`

## Costs
Claude Code subscription · Whisper/ffmpeg free · AI backgrounds = ElevenLabs credits per Veo clip
(`BROLL_PROVIDER=none` for presenter-only) · music free (YouTube Audio Library).
