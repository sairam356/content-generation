---
description: Learn a reference Short (format, hook, visuals, layout) and store it in memory/references.md
argument-hint: <youtube short url> [why it matters]
allowed-tools: Bash, Read, Write, Edit
---

Reference: `$ARGUMENTS`

1. Try Gemini first: `python -m pipeline analyze <url> --mode remix --name ref-<videoid>` and `Read projects/ref-<videoid>/brief.json`
   (the `analysis` object: transcript, structure/beats with timings, visual_style, animation_style, colours, on-screen text).
   If that fails (quota, 403, "cannot access"), use the local route: `python -m pipeline inspect <url>` then
   `Read .state/refs/<videoid>/meta.json`, `Read .state/refs/<videoid>/transcript.json` and view
   `.state/refs/<videoid>/frames.jpg` (24 frames in time order) to understand it yourself.
2. Append ONE entry to `memory/references.md` (create from the template at the top of that file if empty):
   url, channel, topic, duration, hook line (original + Telugu gist), structure (beats with seconds), presenter
   framing/layout (where the person is, how big, what is behind), background/animation style, colours, caption
   style, music/sfx, pacing (cuts per 10s), why it works, what to borrow, what NOT to copy (transcript, exact scenes).
3. If the owner said why it matters (e.g. "this layout", "this hook style"), add it under `## Owner notes` in
   `memory/style.md` as a rule for future `/script` and `/edit` runs.
4. Reply with a 5-line summary of what you stored. Never copy the reference transcript into a script.
