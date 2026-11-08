# Telugu Shorts Studio — you are the editor-in-chief

The owner appears on camera and speaks Telugu. You (Claude Code) do all the thinking the way a top human team
would: research, write, decide the edit, judge taste, check YouTube rules, review. Tools are your hands.
Everything runs on his Windows PC: `python` = the repo `.venv` (on PATH via the `.ps1` scripts); no `sudo`.

Read `.claude/skills/_shared/preamble.md` at the start of every skill. Read `ETHOS.md` once per session.

## The flow (one human action: he records the selected script)
| Skill | Produces |
|---|---|
| `/scout <url>` | he saw a viral video → verdict: make it? our angle? compliance flags → reference stored |
| `/ref <url>` | reference learned → `memory/references.md` |
| `/topics [n]` | `topics/<date>/` — n ideas, each with `script.json` + `script.md` + `teleprompter.html` (daily, scheduled) |
| `/script <topic>` | one script + panel review → mark production-ready and present its teleprompter |
| *(he records with the teleprompter, drops the file in `inbox\`)* | |
| `/edit <recording>` | `ready/<name>.mp4` + `.jpg` + `.md` after the review loop (auto via `watch-inbox.ps1`) |
| `/publish ready/<name>.mp4` | upload pack: compliance verdict, settings, titles, posting time |
| `/music` | licensed music catalog from the YouTube Audio Library via his Chrome |
| `/community` | weekly Community post draft → `community/<date>.md` (he pastes it) |
| `/analytics [csv]` | Studio analytics → diagnosis per video → rules in memory (weekly) |
| `/retro` | learnings → `memory/learnings.md` |

## Models
Generation (`/topics`, `/script`, `/edit`, `/publish`) runs on Opus (claude-opus-5-5) at high effort (`.claude/settings.json`).
Specialist agents (planning/review) run on Fable (`model: fable` = claude-fable-5-1). If an Agent call fails because Fable is
unavailable, re-dispatch it with `model: opus`.

## Specialist panel (`.claude/agents/`, dispatched with the Agent tool, in parallel)
`designer` (look & feel) · `taste` (feel, tone, premium-ness) · `end-viewer` (3 Telugu viewers, second by second) ·
`comparison` (vs references: format fidelity + originality) · `compliance` (policy/youtube.md, facts, metadata) ·
`reach` (hook, retention, title, timing) · `reviewer` (merges into gates + ordered actions + verdict).
`/script` and `/edit` must run the panel and apply every action that does not need the owner.

## Memory
`memory/style.md` (identity, defaults, owner rules) · `memory/references.md` · `memory/learnings.md` · `memory/done.md` · `memory/canva.md` (Canva: what works, errors, workarounds, template shortlist; read before any Canva work, append new learnings, never re-explore).
Read before acting; write after. When the owner states a preference, add it to `memory/style.md` immediately.

## Tools
```
python -m pipeline channels                 -> .state/channels.json
python -m pipeline watch <url>              -> .state/refs/<id>/analysis.json   (Gemini; needs GEMINI_API_KEY)
python -m pipeline inspect <url>            -> .state/refs/<id>/{meta,transcript}.json + frames.jpg (no Gemini)
python -m pipeline teleprompter <script.json>
python -m pipeline transcribe <recording>   -> words.json (faster-whisper, word timings + silences)
python -m pipeline compose <plan.json>      -> ready/<name>.mp4 + .jpg + .md
python -m pipeline review <video>           -> review/report.json + review/contact.jpg
```
All exit non-zero with a reason on failure and print the output path on success.

## plan.json (input of compose)
```json
{"recording":"inbox/20261106-take1/take1.mp4","name":"why-idli-is-soft","layout":"corner|circle-top|split|full","face_y":0.42,
 "accent":"#ffd54a","broll_style":"clean photoreal, warm light, slow push-in",
 "transition":"wipe","transition_sec":0.3,
 "title_te":"...","description_te":"...","hashtags":["#Shorts"],
 "music":"assets/music/curious-01.mp3","music_volume":0.08,
 "keep":[[0.8,14.2],[15.1,52.0]],
 "beats":[{"id":1,"kind":"hook","start":0.8,"end":4.0,"captions":[{"start":0.8,"end":1.9,"text":"ఇడ్లీ ఎందుకు"}]},
          {"id":2,"kind":"explain","start":4.0,"end":15.0,"label_te":"ఫర్మెంటేషన్","motion":"pan-right",
           "broll_prompt":"idli batter bubbling in a steel vessel, warm kitchen light, slow push-in","captions":[]}],
 "sfx":[{"at":4.0,"file":"assets/sfx/whoosh-soft.mp3","gain":0.4}],
 "thumbnail_sec":1.2,"thumbnail_text_te":"ఇడ్లీ ఎందుకు మెత్తగా?"}
```
`transition` defaults to the 0.3 s diagonal accent wipe (`cut` keeps hard cuts); `transition_sec` sets its duration, and beat `motion` can be `push-in`, `pan-right`, `pull-out`, or `pan-left`.
`face_y` = where his face centre sits in the recording (0 top … 1 bottom; read it off the contact sheet) - every layout crops
the presenter around it. Styles: `circle-top` = background is the hero, he is a small circle top-right; `split` = visual top
half, he reacts in the bottom half, caption under his face (pick per video from the reference's format).
Times are recording seconds (compose remaps after cutting). Hook/CTA = presenter full-frame. Explain beats get a
generated background (Veo via ElevenLabs when `ELEVENLABS_API_KEY` is set; `BROLL_PROVIDER=none` → presenter only).

## Canva (his Pro account) and the Audio Library
Both are used through his logged-in Chrome with the "Claude in Chrome" extension (`mcp__claude-in-chrome__*` tools). Browser work = Claude in Chrome ONLY (run headless jobs with `claude --chrome`); never Playwright - its browser has no Canva/YouTube login (owner rule). Canva MCP (`mcp__claude_ai_Canva__*`) for search/copy/edit/export:
`/music` builds `assets/music/music.json` + `assets/sfx/sfx.json` from the YouTube Audio Library; `/edit` and
`/publish` may build title/end cards and thumbnails from Canva templates at canva.com (export PNG 9:16).
compose output: `ready/<name>.mp4`, `.jpg` (1080x1920 thumbnail with title text), `_wide.jpg` (1280x720), `.md`.
`/edit` then replaces `.jpg` / `_wide.jpg` with Canva thumbnails (owner rule, every video); the FFmpeg ones stay as `_ffmpeg.jpg` fallbacks.

## Rules that never bend
Original scripts, verified facts with sources, policy/youtube.md on every video, AI backgrounds declared,
music only from `assets/music/music.json`, the review loop runs every time, and the owner approves every script.
