---
name: ref
description: Learn a reference YouTube Short the way a human editor studies a competitor - format, hook, layout, look, pacing - and store it in memory/references.md. Use when the owner shares a Short URL.
allowed-tools: Bash, Read, Write, Edit, Glob
---
Read `.claude/skills/_shared/preamble.md` first.

## Done means
- `memory/references.md` has a new entry for this URL (no duplicate; update in place if it exists).
- Owner's note (if any) stored as a rule in `memory/style.md` → `## Owner notes`.
- A 5-line summary replied.

## Steps
1. Watch it: `python -m pipeline watch <url>` → `Read .state/refs/<id>/analysis.json`.
   If that fails, `python -m pipeline inspect <url>` → read `meta.json`, `transcript.json`, view `frames.jpg`
   (24 frames in order) and judge it yourself like an editor pausing a video frame by frame.
2. Think like a human editor: what made me stop scrolling? where is the person in the frame and why? what is behind
   him? how fast are the cuts? what do the captions look like? where would I have swiped away? what would I steal
   (format) and what must I never copy (words, scenes)?
3. Write the entry (template at the top of `memory/references.md`): url, channel, topic, duration, hook, beats with
   seconds, layout (corner / circle-top / split / full / other, with sizes), background & animation style, colours,
   captions, music, cuts per 10 s, why it works, borrow / never-copy.
4. If the owner said why it matters ("this layout", "this energy"), add one rule line to `memory/style.md`.
5. Reply with the 5-line summary. Never paste the transcript into any script.
