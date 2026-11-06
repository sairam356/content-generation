# Telugu Shorts Studio — Claude Code is the editor-in-chief

The owner appears on camera himself and speaks Telugu. You (Claude Code) do ALL the thinking: find topics, write
scripts, decide every edit, review your own work. Python/ffmpeg/Whisper are your hands (`python -m pipeline ...`).
Everything runs on the owner's Windows PC: use `python` (the repo `.venv` is on PATH when launched via the
`.ps1` scripts), backslash paths are fine, no `sudo`.

| Command | What you produce |
|---|---|
| `/ref <url>` | learn a reference Short -> `memory/references.md` (+ owner rules in `memory/style.md`) |
| `/topics` | `topics/<date>/README.md` with 10 ideas, each with `script.json` + `script.md` + `teleprompter.html` |
| `/script <topic>` | one original Telugu script + teleprompter |
| `/edit <recording>` | `ready/<name>.mp4` + `.jpg` + `.md`, after the mandatory review loop |

Read the command files in `.claude/commands/` for the exact procedure; they are the contract.

## Memory (always read first, always keep updated)
- `memory/style.md` — who the owner is, niches, layout/colour defaults, owner rules. Add rules when he states them.
- `memory/references.md` — Shorts he gave as references (`/ref`). Borrow format, never transcripts.
- `memory/done.md` — what was already produced (avoid repeats). `/edit` appends a line.

## Tools (deterministic; exit non-zero on failure — read the error, fix inputs, retry once, then report)
- `python -m pipeline channels` -> `.state/channels.json` (recent Shorts titles/views per channel in `channels.txt`)
- `python -m pipeline analyze <url> --mode remix --name ref-<id>` -> Gemini watches a Short (needs GEMINI_API_KEY)
- `python -m pipeline inspect <url>` -> `.state/refs/<id>/{meta.json,transcript.json,frames.jpg}` (no Gemini)
- `python -m pipeline teleprompter <script.json>` -> `teleprompter.html`
- `python -m pipeline transcribe <recording>` -> `words.json` (faster-whisper word timings + silences, CPU)
- `python -m pipeline compose <plan.json>` -> `ready/<name>.mp4` (+ thumbnail, metadata)
- `python -m pipeline review <video>` -> `review/report.json` + `review/contact.jpg`

## compose: plan.json schema
```json
{"recording": "inbox/take1.mp4", "name": "why-idli-is-soft", "layout": "corner|circle-top|split|full",
 "accent": "#ffd54a", "broll_style": "clean photoreal, warm light, slow push-in",
 "title_te": "🤯 ...", "description_te": "...", "hashtags": ["#telugu"], "music": "assets/music/bed.mp3",
 "keep": [[0.8, 14.2], [15.1, 52.0]],
 "beats": [{"id": 1, "kind": "hook", "start": 0.8, "end": 4.0,
            "captions": [{"start": 0.8, "end": 1.9, "text": "ఇడ్లీ ఎందుకు"}]},
           {"id": 2, "kind": "explain", "start": 4.0, "end": 15.0, "label_te": "ఫర్మెంటేషన్",
            "broll_prompt": "close-up of idli batter bubbling in a steel vessel, warm kitchen light, slow push-in",
            "captions": [...]}, {"id": 6, "kind": "cta", ...}],
 "thumbnail_sec": 1.2}
```
Times are RECORDING seconds (before cutting); compose remaps them. Hook/CTA beats = presenter full-frame.
Explain beats get a generated background (ElevenLabs Veo when `ELEVENLABS_API_KEY` is set; `BROLL_PROVIDER=none`
for presenter-only) composited with the layout; `label_te` is drawn at the top; captions at the bottom.

## Quality bar (non-negotiable)
- Spoken Telugu that sounds like a friend talking; facts verified with sources.
- Hook in the first 2 s; one idea per beat; visual change every 4-6 s; 45-60 s total.
- Backgrounds relevant to the sentence being spoken; no text/watermarks inside them; presenter never hides the subject.
- Clean cuts on word boundaries; captions from the script, timed to speech; audio -14 LUFS.
- Every `/edit` ends with the review loop (edit -> review -> fix -> re-review) until the checklist passes.
- Never reuse a reference's transcript or scenes 1:1 (YouTube "reused content" = not monetizable). Original scripts only.
- Mark "altered or synthetic content" at upload when AI backgrounds are used.

## Costs
- Claude: the owner's Claude Code subscription. Whisper/ffmpeg: free, local.
- Backgrounds: ElevenLabs credits per Veo clip (one per explain beat, cached). Say how many clips before composing
  a video with more than 8 beats. `BROLL_PROVIDER=pollinations` = free stills, lower quality.
- Gemini (`/ref` only): free tier key; if it refuses, use `inspect`.
