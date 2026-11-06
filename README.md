# Telugu Shorts Studio (Windows + Claude Code)

You pick a topic, read it to the camera, drop the file in a folder. Claude Code does the rest — and it decides
what to make in the first place.

```
channels.txt (10+ channels)  + web research
        │  /topics  (Claude Code, every morning)      -> topics\<date>\  10 ideas, each with script + teleprompter
        ▼
you pick 2, open teleprompter.html, record on phone/laptop
        │  drop the video into inbox\
        ▼
watch-inbox.ps1 -> claude -p "/edit <file>"
        │  transcribe (Whisper, word timings) -> Claude decides cuts/beats/captions -> compose (ffmpeg):
        │  relevant animated background per beat (Veo via ElevenLabs credits), presenter layout
        │  (corner / circle-top / split / full), Telugu captions, title card, labels, -14 LUFS, then REVIEW loop
        ▼
ready\<name>.mp4  +  <name>.jpg (thumbnail)  +  <name>.md (title, description, hashtags)
```

Memory: `memory\style.md` (your rules), `memory\references.md` (Shorts you gave with `/ref <url>`),
`memory\done.md` (what's made). Claude reads them before every command.

## Setup (once, PowerShell, not as admin)
```powershell
git clone https://github.com/sairam356/content-generation C:\Users\<you>\content-generation
cd C:\Users\<you>\content-generation
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup\setup-windows.ps1          # git/python/node/ffmpeg via winget, .venv + deps, Claude Code, Whisper model
notepad .env                        # ELEVENLABS_API_KEY (backgrounds), GEMINI_API_KEY (optional, for /ref)
notepad channels.txt                # your inspiration channels, one per line
claude                              # log in once
```

## Daily use
| Step | How |
|---|---|
| Teach it a reference | in `claude`: `/ref https://www.youtube.com/shorts/... this layout, this hook style` |
| Topics + scripts | `.\daily-topics.ps1` (or scheduled: `.\setup\register-daily-task.ps1 -At 07:30 -Watcher`) -> opens `topics\<date>\README.md` |
| Record | open `topics\<date>\<nn>-<slug>\teleprompter.html` (SPACE starts scrolling), film yourself 9:16, good light |
| Edit | copy the video into `inbox\` (watcher running) or in `claude`: `/edit inbox\take.mp4 topics\...\script.json --layout circle-top` |
| Result | `ready\<name>.mp4` + thumbnail + metadata; upload, tick "altered or synthetic content" when AI backgrounds are used |

Layouts: `corner` (you lower-left over the background — Osm Dhruva look), `circle-top` (you in a round frame at the
top), `split` (background top / you bottom), `full` (you only). Set the default in `memory\style.md`.

## Tools Claude uses (you can run them too)
```
python -m pipeline channels | inspect <url> | teleprompter <script.json> | transcribe <video> | compose <plan.json> | review <video>
```
Older helpers kept: `analyze` (Gemini watches a Short, used by `/ref`), `tts` / `voice` (ElevenLabs narration if you
ever want a voice-over instead of your own recording), `assemble`.

## Costs
Claude Code subscription; Whisper + ffmpeg free; backgrounds = ElevenLabs credits per Veo clip (set
`BROLL_PROVIDER=none` for presenter-only, `pollinations` for free stills).
