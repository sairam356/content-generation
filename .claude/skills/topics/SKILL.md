---
name: topics
description: Daily topic board - 10 fresh, original ideas WITH complete Telugu scripts and teleprompters, each in the style of one of the owner's channels. Runs scheduled (headless) or on demand.
allowed-tools: Bash, Read, Write, Edit, Glob, WebSearch, WebFetch, Agent
---
Read `.claude/skills/_shared/preamble.md` first. Arguments: `[count] [focus words]` (default 10).

## Done means
- `topics/<YYYY-MM-DD>/README.md` table of N ideas with category, channel style, hook, why it travels, sources.
- Each idea folder `topics/<date>/<nn>-<slug>/` has `script.json` (approved: false), `script.md`, `teleprompter.html`.
- No idea repeats `memory/done.md`, an earlier `topics/*/README.md` from the last 30 days, or another idea today.
- Reply = the table + "Pick 2, read them, tell me 'approved <nn>'".

## Steps (think like a content lead planning the week)
1. Read `memory/style.md`, `memory/learnings.md`, `memory/done.md`, `memory/references.md`.
2. `python -m pipeline channels` → `Read .state/channels.json`. For each channel write one line: niche, voice,
   title pattern, what is getting views right now (sort by views). The owner's channels cover DIFFERENT niches
   (facts, problems, food, daily habits, tech, inventions, India, inspiration, K-culture): each idea inherits
   the niche and voice of the channel that inspired it.
3. Research like a human who reads the internet for a living: 10-15 WebSearch queries, India/Telugu audience
   first, this week's material: funny, interesting, annoying, problematic, new inventions, new problems,
   India-focused silly moments, tech, inspiration stories, Korean/K-culture inspiration, common questions
   ("why does", "how to", "is it true"). Keep source URLs. Prefer specific, checkable, surprising.
4. Shortlist 2x N, then cut to N with a human gut-check per idea: would I stop scrolling for this? can he say it
   with his face? is there a payoff in 45 s? is it safe (policy/youtube.md)? mix categories; no near-duplicates.
5. For each idea run the `/script` procedure (same output), folder `topics/<date>/<nn>-<slug>/`.
6. Write the README table; reply with it.
