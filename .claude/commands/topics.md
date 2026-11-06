---
description: Daily topic board - 10 fresh ideas WITH full Telugu scripts, in the style of the owner's channels
argument-hint: [count=10] [focus words]
allowed-tools: Bash, Read, Write, Edit, WebSearch, WebFetch
---

Goal: `topics/<today>/README.md` with 10 ideas (unless `$ARGUMENTS` says otherwise), each already scripted so the
owner just picks and records.

1. `Read memory/style.md`, `Read memory/references.md`, `Read memory/done.md` (skip anything already made or listed).
2. `python -m pipeline channels` then `Read .state/channels.json`. For EACH channel work out its topic area and
   voice from its recent titles (one line each) - the owner's channels cover different niches (facts, problems,
   food, daily habits, tech, ...); ideas must match the niche of the channel they are inspired by.
3. Research with WebSearch (10-15 searches, India/Telugu-speaking audience first): what people find
   funny / interesting / annoying / problematic / new inventions / new problems / India-focused silly things /
   tech / inspiration stories / Korean (K-culture) inspiration around those niches this week. Prefer specific,
   checkable facts with a source URL. Collect common questions people ask (forums, comments, "why does", "how to").
4. Pick the 10 strongest hooks: curiosity question or bold claim in the first 2 seconds, one clear payoff,
   something to say in a reaction face. Mix categories. No duplicates of memory/done.md or of each other.
5. For each idea run the `/script` procedure (same file format) into `topics/<today>/<nn>-<slug>/script.json`
   + `script.md` + `teleprompter.html` (`python -m pipeline teleprompter <script.json>`).
6. Write `topics/<today>/README.md`: table of nn | category | channel style | hook_te | why it will travel |
   sources, then "Pick 2 and record". Reply with that table.
