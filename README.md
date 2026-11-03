# content-generation — Telugu AI-presenter Shorts from any YouTube Short

Give it a YouTube Short you like. It watches it, understands the concept, writes an **original Telugu
script**, speaks it in **your cloned voice**, renders **you** as the presenter (with b-roll / animation where
the reference used it) and stitches a 9:16 Short with Telugu captions. Everything runs on your **Windows PC**.

```
YouTube Short URL
   │  Gemini (watches the video: transcript, concept, animation style, structure)
   ▼
projects/<p>/brief.json  ── Telugu scene script (presenter / b-roll scenes, visual prompts)
   │  ElevenLabs eleven_v4 — your Instant Voice Clone, language=te, + ffmpeg "deep" mastering
   ▼
projects/<p>/audio/scene_<id>.wav
   │  Claude Code  +  Higgsfield (CLI / MCP): Soul ID of your face → start frames → Seedance lip-sync clips, b-roll
   ▼
projects/<p>/clips/*.mp4  →  ffmpeg assemble (1080x1920, captions in Nirmala UI)  →  projects/<p>/final.mp4
```

## What you need

| Service | Why | Cost note |
|---|---|---|
| Google AI Studio key (`GEMINI_API_KEY`) | video understanding + Telugu script | free tier works for text/video-in |
| ElevenLabs key (`ELEVENLABS_API_KEY`) | clone your voice, Telugu TTS (eleven_v4) | Starter plan or higher for Instant Voice Cloning |
| Higgsfield **paid** subscription | face identity (Soul ID), lip-sync video (Seedance 2.5), b-roll | credits per generation (~80 credits / 5 s talking clip) |
| Claude Code (Anthropic account) | orchestrates Higgsfield, downloads clips, assembles | Pro/Max or API billing |
| Windows 10/11 with winget | — | — |

## Setup (once)

```powershell
git clone https://github.com/sairam356/content-generation.git
cd content-generation
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\setup\setup-windows.ps1          # installs Python, Node, ffmpeg, Claude Code, Higgsfield CLI, Python deps
notepad .env                       # GEMINI_API_KEY, ELEVENLABS_API_KEY
higgsfield auth login              # browser sign-in to your Higgsfield account
claude                             # first launch: sign in. Optional: /mcp -> authenticate "higgsfield"
```

Then put yourself in:

- `assets\me\photos\` — 5-20 clear photos of you (front, 3/4, both sides, one full-body; no sunglasses).
- `assets\me\voice\`  — 1-3 recordings, 1-3 minutes total, quiet room, your normal energetic Telugu voice
  (read a short script the way you'd present). `.wav` or `.mp3`.

```powershell
.\.venv\Scripts\python -m pipeline voice clone      # -> ELEVENLABS_VOICE_ID written to .env
.\.venv\Scripts\python -m pipeline voice preview    # listen: .state\preview.wav
```

The first `/make-short` run will also train your Higgsfield **Soul ID** (asks before spending credits) and
save it to `.env` as `HIGGSFIELD_SOUL_ID`.

## Make a Short

```powershell
.\run.ps1 -Url https://www.youtube.com/shorts/XXXXXXXXXXX
```

1. Gemini writes `projects\<p>\brief.md` — open it, edit any Telugu line you want, save.
2. ElevenLabs renders `audio\scene_<id>.wav` in your voice (re-run `python -m pipeline tts <p> --force` after edits).
3. Claude Code opens with `/make-short projects\<p>`; it shows the Higgsfield credit estimate, waits for your
   "go", generates frames + clips, writes `timeline.json`, and runs the assembler.
4. Result: `projects\<p>\final.mp4` (+ `caption_te` and hashtags in `brief.json` for the upload).

Useful variants:

```powershell
.\run.ps1 -Url <url> -BriefOnly                         # just the analysis + Telugu script
.\run.ps1 -Project projects\<p> -SkipAnalyze            # resume after editing the script
.\run.ps1 -Url <url> -VoicePreset clean                 # less bass/compression
.\run.ps1 -Url <url> -Headless                          # non-interactive Claude (after /mcp + auth done once)
python -m pipeline assemble projects\<p> --music assets\music\bed.mp3
```

Prefer Claude Desktop over Claude Code? See [docs/claude-desktop.md](docs/claude-desktop.md).

## Daily inspiration

Add channels to `channels.txt`, then either run `python -m pipeline daily` or register the scheduled task:

```powershell
.\setup\register-daily-task.ps1 -At 07:30
```

Every morning the newest Shorts of those channels are briefed (Gemini only — no paid video generation).
Pick the ones you like and run `.\run.ps1 -Project projects\<p> -SkipAnalyze`.

## Voice: make it strong

- The clone is only as good as the sample: record close to the mic, chest voice, slightly slower than normal,
  with the energy you want in the Shorts. Avoid music/echo.
- `VOICE_ENHANCE_PRESET=deep` (default) adds low-end warmth, presence and broadcast compression, normalised to
  -14 LUFS (YouTube loudness). `clean` is lighter, `none` is raw ElevenLabs output.
- Want to compare with a designed "news-anchor" voice? `python -m pipeline voice design` makes three
  previews in `.state\voice_design\`; save one with `design-save <n>` and use `--voice-id` on `tts`.
- `delivery` per scene in `brief.json` is written for you; eleven_v4 reacts to punctuation and to tags such as
  `[excited]`, `[whispers]`, `[pause]` placed inside `narration_te` if you want more drama.

## Layout

```
pipeline/analyze.py    Gemini: YouTube URL -> brief.json (analysis + Telugu scene script)
pipeline/voice.py      ElevenLabs clone / design / TTS + ffmpeg mastering presets
pipeline/assemble.py   ffmpeg: clips + narration + captions -> final.mp4
pipeline/daily.py      newest Shorts from channels.txt -> briefs
CLAUDE.md              instructions Claude Code follows for Higgsfield
.claude/commands/make-short.md   the /make-short slash command
.mcp.json              Higgsfield MCP server (https://mcp.higgsfield.ai/mcp) for Claude Code
setup/                 setup-windows.ps1, register-daily-task.ps1
run.ps1                end-to-end runner
```

## Free local renderer (no Higgsfield)

```powershell
.\setup\setup-wav2lip.ps1          # once: Wav2Lip + weights into tools\Wav2Lip (CPU; add -Cuda for a >=4 GB NVIDIA GPU)
# record a 20-30 s vertical phone video of yourself: face well lit, looking at the lens, mouth relaxed, small natural
# head movement, no talking -> assets\me\video\base.mp4
.\run.ps1 -Url https://www.youtube.com/shorts/...     # analyze -> tts -> render -> assemble (Renderer=local is default)
python -m pipeline render projects\<p>                  # or step by step
python -m pipeline assemble projects\<p>
```

Presenter scenes = your video lip-synced by Wav2Lip to the ElevenLabs narration; b-roll = Gemini-generated 9:16
images with a slow zoom; `presenter_overlay` = you in the lower corner over the b-roll (the facts-channel look).
Rendering a 45 s Short takes a few minutes on a laptop CPU. Lip quality is "phone video", not cinematic — switch
to `-Renderer higgsfield` (paid) when you want Seedance-grade clips.

## Offline check

`python smoke_test.py` — no keys or credits (set `SMOKE_FACE=<photo>` to also exercise the Wav2Lip renderer): mocked Gemini brief, synthetic audio through the mastering chain,
synthetic clips assembled to `projects\smoke-test\final.mp4` with Telugu captions.

## Notes

- Only clone your own face and voice. Keep the facts in `analysis.facts_to_verify` honest before publishing.
- Narration per scene should stay under 10 s (video models render 5 s / 10 s clips); `tts` warns otherwise.
- Higgsfield model names change; Claude checks `higgsfield model get <model>` live before each job.
