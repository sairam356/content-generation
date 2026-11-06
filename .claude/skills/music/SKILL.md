---
name: music
description: Build the licensed background-music catalog from the YouTube Audio Library using the owner's logged-in Chrome (Claude in Chrome). Picks tracks per mood like a human music supervisor and writes assets/music/music.json.
allowed-tools: Bash, Read, Write, Edit, Glob, mcp__claude-in-chrome__*
---
Read `.claude/skills/_shared/preamble.md` first. Argument: `[moods] [count per mood]` (default: upbeat, curious, calm, dramatic × 3).

## Why
Only YouTube Audio Library tracks (free, cleared for monetized videos) are allowed (`policy/youtube.md`). The
library has ~10,000 tracks and sits behind the owner's Google login, so you browse it in HIS Chrome.

## Done means
- `assets/music/<slug>.mp3` + `assets/sfx/*` downloaded (moved from the Downloads folder) and
  `assets/music/music.json` = [{file, title, artist, mood, genre, bpm, duration_sec, attribution_required:false,
  source:"YouTube Audio Library", picked_for:"..."}].
- Reply: the table of picks.

## Steps (think like a music supervisor choosing beds for talking-head Shorts)
1. Claim the `music` workflow using the shared one-owner rule. If another live music owner exists, do not browse,
   download, move files or write catalogs; monitor that owner instead. Always select the connected Windows Chrome
   browser automatically (never Mac, never ask). Then check: Chrome tools available? If `mcp__claude-in-chrome__*` is missing: tell the owner to install the "Claude in
   Chrome" extension, run `claude` with `/chrome` enabled, and stop.
2. Open `https://studio.youtube.com` → left menu "Audio Library" → "Free music" tab. Filters: Attribution
   required = "Not required"; Vocals = none (instrumental); Duration 1-3 min; then per mood use the Mood filter
   (upbeat → Happy/Bright; curious → Inspirational/Funky; calm → Calm; dramatic → Dramatic/Dark).
3. For each mood, scan the list like a human: skip anything with a strong melody that fights speech, pick beds
   with steady rhythm, low-mid energy, no sudden hits; prefer 90-120 BPM for upbeat, < 90 for calm. Preview 3-5,
   choose `count` per mood. Note title, artist, genre, mood, duration.
4. Click Download for each; move the files from the Downloads folder into a run-specific
   `.state/music_staging/<run-id>/` first. Never move a download another live session may own. After all picks are
   analyzed and validated, atomically move only this run's final files into `assets/music/`.
5. Sound effects: Audio Library → "Sound effects" tab. Pick like an editor building a kit: 3 whooshes (short, soft),
   3 pops/clicks (for labels), 2 risers (for the twist beat), 2 subtle impacts, 1 "ding". Download into
   `assets/sfx/` and write `assets/sfx/sfx.json` = [{file, title, kind: whoosh|pop|riser|impact|ding, duration_sec}].
6. Write `music.json`; add one line to `memory/style.md` → Owner notes if he expressed a taste.
