---
name: publish
description: Final pre-upload pack for a ready video - compliance verdict, upload settings, title/description/hashtags variants, best posting time, thumbnail check. Does not upload.
allowed-tools: Bash, Read, Write, Edit, Glob, Agent, WebSearch
---
Read `.claude/skills/_shared/preamble.md` first. Argument: `ready/<name>.mp4` (or the name).

## Done means
- `ready/<name>.publish.md`: VERDICT (publishable / blocked + why), exact upload settings (audience, altered-or-
  synthetic, category, language te), 3 title options + chosen, description (with sources + disclaimer when
  needed), hashtags, pinned comment, 2 posting slots (IST), thumbnail note.
- Reply with the verdict and the chosen title.

## Steps
1. Read `ready/<name>.md`, the plan/script it came from, `policy/youtube.md`.
2. Agents in parallel: `compliance` (final), `reach` (title/description/time), then `reviewer`.
3. Write the pack. If BLOCKED, say exactly what to change and which skill fixes it.
