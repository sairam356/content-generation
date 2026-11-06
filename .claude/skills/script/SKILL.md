---
name: script
description: Write one original Telugu Short script (hook -> beats -> CTA) with per-beat visuals, verified facts, title/description/hashtags and a teleprompter; then run the specialist panel and STOP for the owner's approval.
allowed-tools: Bash, Read, Write, Edit, Glob, WebSearch, WebFetch, Agent
---
Read `.claude/skills/_shared/preamble.md` first. Arguments: `<topic or idea> [--style <channel>] [--sec 45-60] [--out <folder>]`.

## Done means
- `<folder>/script.json` (schema below, `"approved": false`), `script.md`, `teleprompter.html`.
- Specialist panel run (reach, taste, compliance, end-viewer, comparison → reviewer) and every FIX applied; verdict APPROVE
  or the remaining BLOCK stated honestly.
- Reply: hook + beats (6 lines), the reviewer verdict, then STOP: "Read `<folder>/script.md`; say 'approved' or
  what to change." Never set `approved` yourself.

## Steps (write like a human writer who has to say this on camera)
1. Read `memory/style.md`, `memory/learnings.md`, `memory/references.md` (format only).
2. Verify facts: 2-4 sources (official / reputable / Indian when relevant); keep URLs; drop anything unsourced.
3. Draft in spoken Telugu (Telugu script; English words in English letters as people say them). Budget 45-60 s
   ≈ 110-140 words at 2.3 words/s. Shape:
   - hook_te: ONE sentence ≤ 12 words, topic + tension, said to camera.
   - 4-6 beats, 15-30 words each, one idea each, a number/surprise in ≥ 3 beats, last beat = twist / tip / "what it
     means for you". Each beat: `broll_prompt` (ENGLISH, concrete scene behind the presenter: subject, motion,
     light; no text, no faces), `label_te` (2-4 words), `delivery` (pace, face, gesture).
   - cta_te: short, asks a question back (comments).
   - title_te (≤ 60 chars, honest, emoji only if the style uses it), description_te (2 lines + question + sources
     + health/money disclaimer when policy requires), hashtags (8-12 incl. #Shorts), thumbnail_idea.
4. Read it aloud in your head as him: cut anything that sounds written, not spoken.
5. Specialist panel (Agent tool, in parallel): `reach`, `taste`, `compliance`, `end-viewer`, `comparison`. Then `reviewer`
   with their four reports. Apply every action from the reviewer that does not need the owner. If BLOCK remains,
   say why in the reply.
6. Save `script.json`, `script.md` (hook, beats, CTA, title/description/hashtags, sources, panel verdict), run
   `python -m pipeline teleprompter <folder>/script.json`.
7. STOP for approval (human gate). In headless mode just leave `approved: false` and report.

## script.json
```json
{"topic":"...","style_channel":"...","category":"...","title_te":"...","hook_te":"...",
 "beats":[{"id":1,"text_te":"...","broll_prompt":"...","label_te":"...","delivery":"..."}],
 "cta_te":"...","description_te":"...","hashtags":["#Shorts"],"thumbnail_idea":"...","sources":["url"],
 "music_mood":"curious|upbeat|calm|dramatic|none","est_sec":52,"approved":false,"panel_verdict":"APPROVE"}
```
