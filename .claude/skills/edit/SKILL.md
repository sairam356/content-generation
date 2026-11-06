---
name: edit
description: Pro edit of the owner's recording into ready/<name>.mp4 - cut like a human editor, relevant animated backgrounds, chosen layout, Telugu captions, music, then a strict review loop with the specialist panel. Refuses scripts that are not approved.
allowed-tools: Bash, Read, Write, Edit, Glob, Agent, mcp__claude-in-chrome__*
---
Read `.claude/skills/_shared/preamble.md` first. Arguments: `<recording> [script.json] [--layout corner|circle-top|split|full] [--no-script]`.

## Done means
- `ready/<name>.mp4`, `ready/<name>.jpg`, `ready/<name>.md` exist (paths listed, duration stated).
- Review loop finished: `python -m pipeline review` facts + specialist panel (designer, end-viewer, compliance,
  reach, comparison → reviewer) and the checklist below all PASS, or the remaining issue is stated.
- `memory/done.md` has a new line. Reply: what you cut, layout, backgrounds used, music, anything to re-record.

## Gate
Find the script: given, else newest `topics/*/*/script.json` whose hook matches the first sentence spoken
(compare after transcription). If `approved` is not true and `--no-script` was not passed: STOP and say
"script <path> is not approved - say 'approved' or run with --no-script". Headless: report and exit.

## Steps (work like a senior Shorts editor would today)
1. Context: `memory/style.md`, `memory/references.md`, `memory/learnings.md`, the script.
2. `python -m pipeline transcribe <recording>` → `Read words.json`. Whisper's Telugu spelling is unreliable:
   captions come from the SCRIPT; Whisper gives timing only. Map each script sentence to its words.
3. Decide the cut as a human would - watch for: dead air, breaths > 0.6 s, false starts, repeated takes (keep the
   LAST good one), coughs, "umm", the eyes-reading-the-prompter pause before a sentence. Cut on word boundaries,
   leave ~0.15 s of air. Hook starts within 0.3 s of the video start. Target the script's est_sec (45-60 s).
4. Beats: hook / explain… / cta with start-end in recording seconds; captions 2-4 words, ≥ 0.4 s, never
   overlapping, from the script text. `label_te` and `broll_prompt` from the script (adapt the prompt if he said
   something different). Layout from args → `memory/style.md` default. Hook and CTA are presenter full-frame.
5. Music: if the script's `music_mood` is not `none` and `assets/music/music.json` exists, pick the track a human
   would (mood match, no vocals, not used in the last 3 videos per `memory/done.md`); set `music` + `music_volume`
   (0.06-0.10). No catalog → no music (never download random music).
6. Sound design like a pro editor (only from `assets/sfx/sfx.json`; none → skip): a soft whoosh on the hook→beat-1
   transition and on layout changes, a pop when a label appears (first explain beat and the twist beat), a riser
   into the twist beat, never more than one SFX per 3 s, gains 0.3-0.5. Put them in `plan.sfx`
   ([{at: recording_sec, file, gain}]). Thumbnail: `thumbnail_text_te` = the hook in ≤ 6 words, `thumbnail_sec` =
   the frame where his face is most expressive (pick from the contact sheet after the first compose).
   Canva (optional, via Chrome tools `mcp__claude-in-chrome__*`, his Pro account at canva.com): when a title card,
   end card or thumbnail would look better from a template, build it there (9:16, export PNG) into
   `<folder>/canva/` and reference it from the plan as `title_card` / `end_card` / use it as the thumbnail.
7. Write `<folder>/plan.json` (schema in CLAUDE.md) and run `python -m pipeline compose <folder>/plan.json`.
   Backgrounds: Veo via ElevenLabs credits per explain beat (cached per beat id). > 8 beats: say the count first.
8. Review loop (mandatory, max 3 rounds):
   a. `python -m pipeline review ready/<name>.mp4`; view `review/contact.jpg`.
   b. Panel (Agent, parallel): `designer`, `taste`, `end-viewer`, `compliance`, `reach`, `comparison`; then `reviewer`.
   c. Checklist: hook < 0.3 s & full-frame & title readable · every cut clean (no clipped words, no mid-sentence
      jump, no black/frozen frames) · captions correct + in sync (spot-check 3) + never over the face · each
      background relevant to the sentence, no text/watermark, presenter not hiding the subject · visual change
      every 4-6 s · length within target · audio -14 ± 2 LUFS, no clipping, no silence > 0.8 s · music under the
      voice, licensed · looks like the references.
   d. Anything failing → fix plan.json (or delete `build/bg_<id>*` to regenerate a background) → compose → review.
9. Append to `memory/done.md`: date | name | topic | layout | duration | music | panel verdict. Reply.
