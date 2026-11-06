---
name: analytics
description: Channel-growth analyst. Reads YouTube Studio analytics (CSV export or live via the owner's Chrome), diagnoses each Short (hook swipe-away, retention curve, CTR, comments), names the real problem, and writes concrete rules for content, script and editing into memory so the next videos improve. Weekly or on demand.
allowed-tools: Bash, Read, Write, Edit, Glob, Agent, WebSearch, mcp__claude-in-chrome__*
---
Read `.claude/skills/_shared/preamble.md` first. Argument: a CSV/folder path, a video name, or nothing (= last 7 days).

## Done means
- `analytics/<YYYY-MM-DD>.md`: per video table (views, swipe-away % at 0-3 s, avg % viewed, drop points, CTR,
  likes/comments ratio, traffic source) → diagnosis (ONE main problem each) → fix.
  Channel section: what is working (double down), what is not (stop), 3 experiments for next week.
- `memory/learnings.md` gained evidence-based rules (numbers quoted); `memory/style.md` defaults updated only when
  a pattern repeated ≥ 2 videos. Contradicted old rules fixed, not duplicated.
- Reply: the 5 most important findings in plain language and what changes from tomorrow.

## Getting the data
1. If a CSV/folder is given: read it (YouTube Studio → Analytics → Advanced mode → export: content table + audience
   retention per video).
2. Else, Chrome tools available (`mcp__claude-in-chrome__*`): open `https://studio.youtube.com` → Analytics →
   Content → Shorts; per video open the retention graph ("Shown in feed", "Viewed vs swiped away", "Average
   percentage viewed", "Key moments"); read numbers off the page. No Chrome → ask the owner for the export and stop.
3. Join with `memory/done.md` (hook type, layout, music, length, topic category per video).

## Diagnose like a growth lead, not a dashboard
- Swipe-away high (> 30 % in 0-3 s) → hook/topic/thumbnail-frame problem: quote the first sentence, judge it.
- Retention cliff at one point → look at that beat in the script: too long, no new info, bad background, reading voice.
- Avg % viewed < 70 % on 45-60 s → pacing/length; > 90 % with low views → distribution/topic breadth, not the edit.
- Low likes/comments → no question asked, no opinion; high comments on one topic → series opportunity.
- Compare layouts (corner vs circle-top), lengths, categories, posting times across videos; demand ≥ 2 data points
  before calling it a rule; mark single-video observations as "hypothesis".
- Agents: `reach` (retention/hook rewrite ideas), `taste` (is it a feel problem?), `reviewer` to merge.

## Write back
- learnings.md: `date | video | metric evidence | rule (content / script / editing)` - one line each, specific.
- style.md: change a default (layout, length, hook pattern, caption size) only with repeated evidence; note why.
- topics/script/edit read these files first, so the next videos implement the rules automatically.
