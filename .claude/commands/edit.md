---
description: Pro edit of the owner's recording -> ready/<name>.mp4 (strict quality loop: edit, review, fix, re-review)
argument-hint: <recording.mp4> [script.json] [--layout corner|circle-top|split|full]
allowed-tools: Bash, Read, Write, Edit
---

You are a top-tier Shorts editor. Input: `$ARGUMENTS` (a recording the owner made of himself reading a script).
Output: `ready/<name>.mp4` + `.jpg` + `.md`, and you only stop when it passes the checklist below.

## 1. Understand
- `Read memory/style.md`, `Read memory/references.md` (layout/visual rules), the script.json if given (else find
  the newest `topics/*/*/script.json` whose hook matches the speech).
- `python -m pipeline transcribe <recording>` -> `Read <folder>/words.json` (words with start/end, silences).
  Whisper's Telugu spelling is unreliable; use the SCRIPT text for captions, Whisper only for timing.

## 2. Decide the cut (write `<folder>/plan.json`)
- keep: list of [start,end] in recording seconds. Remove: leading/trailing dead air, silences >= 0.6 s (keep
  ~0.15 s breath), false starts and repeated takes (keep the LAST good take of a sentence), coughs, "umm".
  Never cut inside a word (snap to word boundaries from words.json). Target 45-60 s total unless the script
  says otherwise; Shorts hard max 180 s.
- beats: map the speech to the script beats using word timings: {id, kind: hook|explain|cta, start, end,
  label_te, broll_prompt, captions:[{start,end,text}]}. Captions: 2-4 words each, text from the script, timed
  by the matching words; a caption never overlaps the next; keep each >= 0.4 s.
- layout: owner's choice from $ARGUMENTS or memory/style.md; default `corner` (presenter lower-left over the
  background, the Osm Dhruva look). `circle-top` = presenter in a round frame at the top, background full.
  Hook and CTA beats are always the presenter full-frame.
- broll_style: one sentence describing the visual family from references (e.g. "clean photoreal, warm, slight
  slow push-in"). title_te, description_te, hashtags from the script. accent colour from memory/style.md.
- plan.json schema: {"recording","name","layout","accent","broll_style","title_te","description_te",
  "hashtags":[],"music":optional path,"keep":[[s,e]],"beats":[...],"thumbnail_sec":optional}

## 3. Build
- `python -m pipeline compose <folder>/plan.json` (cuts, generates background video per explain beat via
  ElevenLabs Veo when ELEVENLABS_API_KEY is set, composites the layout, burns captions + title + labels, masters
  the voice to -14 LUFS, writes thumbnail + metadata). Backgrounds are cached per beat id in `<folder>/build/`.

## 4. Review (mandatory, every time)
- `python -m pipeline review ready/<name>.mp4` and view `<folder>/review/contact.jpg` (30 frames in order).
- Checklist - ALL must pass:
  1. Hook starts within 0.3 s, presenter full-frame, title card readable, no dead air.
  2. Every cut is clean (no clipped words, no jump in the middle of a sentence, no frozen/black frames).
  3. Captions: correct Telugu from the script, timed with speech (spot-check 3 places), never covering the face.
  4. Background per beat is RELEVANT to what is said at that moment and matches the reference style; no text or
     watermark in it; presenter window not covering the key subject.
  5. Pacing: a visual change at least every 4-6 s; total length within target; CTA last and short.
  6. Audio: loudness -14 +-2 LUFS, no clipping, no silence > 0.8 s.
  7. Looks like the references (layout, colours, energy) - compare with memory/references.md.
- If anything fails: fix plan.json (or regenerate a background: delete `<folder>/build/bg_<id>*`), re-run
  compose, re-run review. Repeat until all pass (max 3 rounds; then report what is still off).

## 5. Finish
- Append a line to `memory/done.md`: date | name | topic | layout | duration | notes.
- Reply: path of ready/<name>.mp4, duration, layout, what you cut, what backgrounds you used, and anything the
  owner should re-record for a better take.
