---
name: retro
description: After a video is published or performance data comes in, extract learnings (what worked, what failed, rules going forward) into memory/learnings.md and adjust memory/style.md. Use weekly or when the owner shares view numbers.
allowed-tools: Bash, Read, Write, Edit, Glob
---
Read `.claude/skills/_shared/preamble.md` first. Argument: free text (numbers, feedback) or nothing (review the last 5 in `memory/done.md`).

## Done means
- `memory/learnings.md` gained 1-5 bullets: date | video | what we tried | what happened | rule going forward.
- Contradicted rules in `memory/style.md`/`learnings.md` were fixed, not duplicated.
- Reply: the new rules in plain language.

## Steps
1. Read `memory/done.md`, `memory/learnings.md`, `memory/style.md`, and the owner's input.
2. Like a channel analyst: which hooks retained, which layouts/backgrounds got comments, what the owner disliked,
   what took too long. Separate evidence (numbers) from guesses; mark guesses.
3. Write the bullets; update style defaults only when evidence repeats twice.
