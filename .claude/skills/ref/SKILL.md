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
1. Always run BOTH evidence passes (independent, not primary/fallback):
   - `python -m pipeline inspect <url>` → hard evidence: YouTube metadata, exact local transcript timings,
     downloaded video and 24 ordered frames.
   - `python -m pipeline watch <url>` → Gemini watches the complete video + audio for motion, delivery,
     scene context, audio mood and why it works. If Gemini is unavailable, mark that analysis incomplete.
2. Reconcile field by field before judging: YouTube/local evidence wins for metadata, timing and a listed music
   title; Gemini supplies continuous visual/audio semantics. For every disagreement, state it and lower confidence;
   never silently choose or invent a music title. Save `evidence: local|gemini|both` and `confidence: high|medium|low`
   in the reference entry.
3. Think like a human editor: what made me stop scrolling? where is the person in the frame and why? what is behind
   him? how fast are the cuts? what do the captions look like? where would I have swiped away? what would I steal
   (format) and what must I never copy (words, scenes)?
4. Write the entry (template at the top of `memory/references.md`): url, channel, topic, duration, hook, beats with
   seconds, layout (corner / circle-top / split / full / other, with sizes), background & animation style, colours,
   captions, music, cuts per 10 s, why it works, borrow / never-copy.
5. If the owner said why it matters ("this layout", "this energy"), add one rule line to `memory/style.md`.
6. Reply with the 5-line summary. Never paste the transcript into any script.
