# content-generation — Telugu AI-presenter Shorts

You (Claude Code) are the production step of this pipeline. Python has already done the thinking:

| Step | Who | Output |
|---|---|---|
| 1. Understand the reference Short + write the Telugu scene script | `python -m pipeline analyze <url>` (Gemini) | `projects/<p>/brief.json` |
| 2. Narration in the owner's cloned voice (Telugu, ElevenLabs eleven_v4) | `python -m pipeline tts <p>` | `projects/<p>/audio/scene_<id>.wav` |
| **3. Generate the visuals with Higgsfield (your job)** | `/make-short projects/<p>` | `projects/<p>/clips/*.mp4`, `timeline.json` |
| 4. Stitch + Telugu captions | `python -m pipeline assemble <p>` | `projects/<p>/final.mp4` |

The owner's face photos live in `assets/me/photos/`. The owner's Soul ID (Higgsfield identity) is
`HIGGSFIELD_SOUL_ID` in `.env` once trained. Everything runs on the owner's Windows PC: use
PowerShell-compatible commands (`python`, not `python3`; paths with `\` are fine; no `sudo`).

## Higgsfield access

Two equivalent routes; prefer the CLI (`higgsfield`) because it uploads local files and downloads results:

- CLI: `higgsfield account status` must show a paid plan. If it says not authenticated, stop and ask the
  owner to run `higgsfield auth login`. Schemas are live: `higgsfield model get <model> --json` and
  `higgsfield model list`. Always check `higgsfield generate cost ...` before the first paid job of a project
  and tell the owner the total estimate for all scenes before continuing.
- MCP (`.mcp.json`, server `higgsfield`): same tools, used when the CLI is missing. Authenticate with `/mcp`.

Model choices (verify with `higgsfield model get` — names change):
- Start frame with the owner's face: `text2image_soul_v2 --soul-id <HIGGSFIELD_SOUL_ID> --aspect_ratio 9:16`
  (fallback `soul_cinematic`). B-roll start frames: `nano_banana_2` or `gpt_image_2_5`, 9:16.
- Talking clip (lip-sync to our wav): `seedance_2_5` with `--start-image <frame> --audio <wav> --aspect_ratio 9:16
  --duration <clip_duration_sec> --generate_audio false`. If `seedance_2_5` rejects audio, use `seedance_2_0`
  (same flags). Never let the model invent speech: the prompt must say "speaks the supplied audio, lips in sync".
- B-roll / animation clip: `gemini_omni` or `kling3_0 --start-image <frame> --sound off`, 9:16, 5 or 10 s.
- Soul ID training (one-time): `higgsfield soul-id create --name me --soul-2 --image <photo>...` with every
  photo in `assets/me/photos` (5-20, varied angles), then `higgsfield soul-id wait <id>` and write the id to
  `.env` as `HIGGSFIELD_SOUL_ID`.

## Rules

- Read `brief.json` fully first. `script.scenes[*]` has `narration_te`, `visual_prompt`, `image_prompt`,
  `clip_duration_sec`, `audio_file`, `audio_duration_sec`. The audio is the source of truth for timing.
- One scene at a time, in order. After each generation, download the result to the paths below and record
  the job id in `projects/<p>/jobs.json` so a re-run never pays twice (skip scenes whose files already exist).
- Presenter scenes: the face must be the owner's (Soul ID). Vertical 9:16, phone-video realism, locked-off
  or slow push-in, hands visible, no on-screen text in the generated video.
- B-roll scenes: follow `visual_prompt`; match the reference's animation style from `analysis.animation_style`
  (e.g. clean motion graphics, 3D, whiteboard). No text, no logos, no faces of real people.
- Use the owner's language: reply in English, keep Telugu strings exactly as written in `brief.json`.
- Do not change the Telugu narration. If a clip is a bad take, regenerate at most once, then move on and
  note it in the final summary.
- Files: `projects/<p>/frames/scene_<id>.png`, `projects/<p>/clips/scene_<id>.mp4`, `projects/<p>/clips/cta.mp4`.
- Finish with `projects/<p>/timeline.json` (see `pipeline/assemble.py` docstring) and run
  `python -m pipeline assemble projects/<p>`; report the path of `final.mp4`, the credits spent, and any
  scene that needs a retake.
