---
name: edit
description: Pro edit of the owner's recording into ready/<name>.mp4 - cut like a human editor, relevant animated backgrounds, chosen layout, Telugu captions, music, then a strict review loop with the specialist panel.
allowed-tools: Bash, Read, Write, Edit, Glob, Agent, mcp__claude-in-chrome__*
---
Read `.claude/skills/_shared/preamble.md` first. Arguments: `<recording> [script.json] [--layout corner|circle-top|split|full] [--no-script]`.

## Done means
- `ready/<name>.mp4`, `ready/<name>.jpg`, `ready/<name>.md` exist (paths listed, duration stated) and
  `ready/<name>.verify.json` says `"ok": true` (complete file, faststart, H.264/AAC, full decode with zero errors).
  A video that is not verified is not done, whatever the panel says.
- Review loop finished: `python -m pipeline review` facts + specialist panel (designer, end-viewer, compliance,
  reach, comparison → reviewer) and the checklist below all PASS, or the remaining issue is stated.
- `memory/done.md` has a new line. Reply: what you cut, layout, backgrounds used, music, anything to re-record.

## Script matching
Find the script: given, else newest `topics/*/*/script.json` whose hook matches the first sentence spoken
(compare after transcription). Recording a panel-reviewed script is acceptance; never stop for a separate approval.
Use `--no-script` only for explicit smoke tests or a genuinely unscripted recording.

## Steps (work like a senior Shorts editor would today)
1. Claim a workflow keyed by the recording's resolved path using the shared one-owner rule. If another live edit
   owns this recording, monitor its log; never launch a second transcription/compose against it. Context:
   `memory/style.md`, `memory/references.md`, `memory/learnings.md`, the script.
2. `python -m pipeline transcribe <recording>` → `Read words.json`. Whisper's Telugu spelling is unreliable:
   captions come from the SCRIPT; Whisper gives timing only. Map each script sentence to its words.
   With `--no-script` (smoke tests only) Whisper's text is the only source and it may be wrong for Telugu:
   write captions by meaning from the audio, say so in `ready/<name>.md`, and never upload without the owner checking them.
3. Decide the cut as a human would - watch for: dead air, breaths > 0.6 s, false starts, repeated takes (keep the
   LAST good one), coughs, "umm", the eyes-reading-the-prompter pause before a sentence. Cut on word boundaries,
   leave ~0.15 s of air. Hook starts within 0.3 s of the video start. Target the script's est_sec (45-60 s).
4. Beats: hook / explain… / cta with start-end in recording seconds; captions 2-4 words, ≥ 0.4 s, never
   overlapping, from the script text. `label_te` and `broll_prompt` from the script (adapt the prompt if he said
   something different). Layout from args → `memory/style.md` default. Hook and CTA are presenter full-frame.
   Transitions (owner decision 2026-11-08): `transition: "sections"` (default) - the 0.3 s diagonal accent wipe only
   where the video changes direction (hook→explain, explain→cta, a new `label_te` = next topic section, or a beat
   marked `"wipe": true`); every
   other beat is a hard cut and its label pill pops in. Cycle background motion `push-in` → `pan-right` → `pull-out`
   → `pan-left`; use a beat's `motion` override when needed. `"wipe"` (every change) only if the reference demands it.
5. Music: if the script's `music_mood` is not `none` and `assets/music/music.json` exists, pick the track a human
   would (mood match, no vocals, not used in the last 3 videos per `memory/done.md`); set `music` + `music_volume`
   (0.06-0.10). No catalog → no music (never download random music).
6. Sound design like a pro editor (only from `assets/sfx/sfx.json`; none → skip): a soft whoosh on the hook→beat-1
   transition and on layout changes, a pop when a label appears (first explain beat and the twist beat), a riser
   into the twist beat, never more than one SFX per 3 s, gains 0.3-0.5. Put them in `plan.sfx`
   ([{at: recording_sec, file, gain}]). Thumbnail: `thumbnail_text_te` = the hook in ≤ 6 words, `thumbnail_sec` =
   the frame where his face is most expressive (pick from the contact sheet after the first compose).
   `face_y` = his face centre as a fraction of the recording height (contact sheet; phone selfies are usually 0.35-0.45) -
   layouts crop around it. Layout per video: `circle-top` when the background subject must stay the hero,
   `split` when the reference format is "visual top / reaction bottom"; never cover his face with a caption.
   Canva (optional, via Chrome tools `mcp__claude-in-chrome__*`, his Pro account at canva.com): when a title card
   or end card would look better from a template, build it there (9:16, export PNG) into `<folder>/canva/` and
   reference it from the plan as `title_card` / `end_card`. The thumbnail is always made in Canva (step 9).
7. Write `<folder>/plan.json` (schema in CLAUDE.md) and run `python -m pipeline compose <folder>/plan.json`.
   Compose renders to a temp file, runs `verify` (atoms, faststart, codecs, full decode) and only then moves it
   atomically into `ready/` - so `ready/<name>.mp4` is never half-written. If compose says "failed verification",
   read the listed errors and fix the cause (plan, inputs, disk); never re-run blindly and never copy the temp
   file into `ready/` by hand.
   Backgrounds: one per explain beat, cached per beat id (`build/bg_<id>.png|mp4`). `BROLL_PROVIDER=pollinations`
   (free, default for tests) allows 1 image per 45 s per IP - compose paces and retries itself, so 10 beats take
   ~8 min; do not run two composes at once. `elevenlabs` = Veo clips on credits; > 8 beats: say the count first.
   If compose exits with `FAILED: no background for explain beat(s) [...]`, that is the gate working: an explain
   beat with the presenter full-frame is not the agreed look. Fix the cause (network, provider limit, prompt) and
   re-run compose (finished backgrounds stay cached). Never set `allow_presenter_fallback` just to get a file out.
8. Review loop (mandatory, max 3 rounds):
   a. `python -m pipeline review ready/<name>.mp4`; view `review/contact.jpg`.
   b. Panel (Agent, parallel): `designer`, `taste`, `end-viewer`, `compliance`, `reach`, `comparison`; then `reviewer`.
   c. Checklist: hook < 0.3 s & full-frame & title readable · every cut clean (no clipped words, no mid-sentence
      jump, no black/frozen frames) · captions correct + in sync (spot-check 3) + never over the face · each
      background relevant to the sentence, no text/watermark, presenter not hiding the subject · visual change
      every 4-6 s · length within target · audio -14 ± 2 LUFS, no clipping, no silence > 0.8 s · music under the
      voice, licensed · looks like the references.
   d. Anything failing → fix plan.json (or delete `build/bg_<id>*` to regenerate a background) → compose → review.
      Each compose replaces `ready/<name>.mp4` atomically after verification; `review` re-checks `verify` too
      (`checks.playable_everywhere`). Finish with `python -m pipeline verify ready/<name>.mp4` and quote its result.
9. Canva thumbnail (owner rule: every video). After the final verify, read `memory/canva.md` first and follow its
   thumbnail workflow (Canva connector `mcp__claude_ai_Canva__*` + Claude in Chrome, never Playwright; designs private):
   - Keep the FFmpeg ones as `ready/<name>_ffmpeg.jpg` / `_wide_ffmpeg.jpg` (copy, don't delete).
   - Owner rule (2026-11-08): pick ONE of two layouts per video. The two parameters are CONTENT (how strong his
     reaction is in the recording, what the hook is about) and TASTE (what the Telugu facts audience clicks; ask the
     `taste` agent when unsure). Decide it in the plan as `thumbnail_layout: "face" | "topic"` and say why in the reply:
     * `face` - only when his reaction in the recording is strong enough to carry the click on its own (a real
       viral-grade expression: shock, laugh, disbelief). His face big (FFmpeg style), `thumbnail_text_te` on top,
       hook number in accent - rebuilt in Canva for the clean text, not the raw FFmpeg frame.
     * `topic` (the default) - the sharpest, most on-topic `build/bg_<id>.png` filling the frame + the hook
       number/word as the biggest element + `thumbnail_text_te` (≤ 5 words) + his face as a small disc
       (≤ 22 % of the width, natural smile, background-removed with `remove-background`), tucked above the number
       bar. Drop the disc only if no frame looks natural. A frozen mid-word face frame is never used.
     Look for both: the shortlist black-and-yellow facts style (accent from plan).
   - Blank design at exact size (`https://www.canva.com/design?create=true&width=1080&height=1920&units=px`), then
     lay out again for 1280x720 (don't use `resize-design`). Keep the bottom 20 % and right edge clear.
   - Export PNG, convert to JPG over `ready/<name>.jpg` (1080x1920) and `ready/<name>_wide.jpg` (1280x720).
   - Put both Canva edit links in `ready/<name>.md`. Append only new Canva findings to `memory/canva.md`.
   - If Canva fails (not connected, export error), restore the FFmpeg thumbnails, say so in the reply and finish -
     the video is never blocked on the thumbnail.
10. Append to `memory/done.md`: date | name | topic | layout | duration | music | panel verdict. Reply.
