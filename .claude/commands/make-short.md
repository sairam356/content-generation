---
description: Generate the Higgsfield visuals for a briefed Telugu Short and assemble final.mp4
argument-hint: projects/<project-folder>
allowed-tools: Bash, Read, Write, Edit
---

Produce the Telugu Short for project `$ARGUMENTS` following CLAUDE.md.

Checklist, in order:

1. `Read $ARGUMENTS/brief.json`. Confirm every scene has `audio_file` (else tell the owner to run
   `python -m pipeline tts $ARGUMENTS` and stop).
2. `higgsfield account status` (must be authenticated, paid plan). Load `HIGGSFIELD_SOUL_ID` from `.env`;
   if empty, train a Soul ID from `assets/me/photos` (ask first: it costs credits and takes ~10 min) and save it.
3. Cost: run `higgsfield generate cost` for one start frame, one presenter clip and one b-roll clip, multiply
   by the scene counts, and show the owner the estimate. Wait for a "go" before generating.
4. For each scene in `script.scenes` (skip if `clips/scene_<id>.mp4` exists):
   a. Start frame 9:16 -> `frames/scene_<id>.png` (`image_prompt`; presenter scenes with `--soul-id`).
   b. Clip -> `clips/scene_<id>.mp4`:
      - presenter / presenter_overlay: Seedance 2.5, `--start-image frames/scene_<id>.png --audio <audio_file>
        --duration <clip_duration_sec> --aspect_ratio 9:16 --generate_audio false`, prompt = `visual_prompt`
        + " He speaks exactly the supplied audio in Telugu, lips in precise sync, natural blinks and gestures."
      - broll: image-to-video from the frame with `visual_prompt`, sound off.
   c. Append `{scene_id, frame_job, clip_job, model, credits}` to `jobs.json`.
5. CTA clip (`script.cta_te`, `cta_audio_file`): one more presenter clip -> `clips/cta.mp4`.
6. Write `timeline.json`:
   `{"items":[{"scene_id":1,"video":"clips/scene_1.mp4","audio":"audio/scene_1.wav","use_clip_audio":false,
   "narration_te":"...","text":"..."}, ...], "burn_subtitles": true}` (include the CTA item last).
7. `python -m pipeline assemble $ARGUMENTS` and report `final.mp4`, total credits, retakes needed.
