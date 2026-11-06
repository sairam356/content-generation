---
name: community
description: Weekly YouTube Community post, written like a creator who talks to his audience - alternates content posts (poll, teaser, behind the scenes) and personal posts (a note from the owner, a question). Drafts to community/<date>.md for approval; never posts.
allowed-tools: Bash, Read, Write, Edit, Glob, Agent, WebSearch
---
Read `.claude/skills/_shared/preamble.md` first. Argument: optional focus ("poll", "personal", "teaser", "bts") or owner notes.

## Done means
- `community/<YYYY-MM-DD>.md`: the post (spoken Telugu, ≤ 120 words), post type, image/frame suggestion
  (path from `ready/` or a Canva idea), poll options if any, best posting time (IST), and 1-line why.
- Specialist check: `taste` + `compliance` (+ `reach` for polls); fixes applied.
- Reply: the post text + type, then "say 'post it' when you've pasted it" (he posts manually).

## Steps (think like a creator keeping a community warm, once a week)
1. Read `memory/done.md` (this week's videos), `memory/learnings.md`, `memory/style.md`, last 4 `community/*.md`
   (alternate: content → personal → content → personal; never the same type twice in a row unless asked).
2. Content types: POLL "which topic next?" with 3 options from the newest `topics/<date>/README.md`;
   TEASER one surprising line from an approved-but-unrecorded script; BTS a real frame from `ready/<name>.jpg`
   with one honest line about making it. Personal types: a short note in his voice (why this topic mattered,
   what he learned, a thank-you with a real number), a question that invites stories in comments.
3. Write it in his spoken Telugu; one emoji max; no hashtags; one clear ask (vote / comment / watch).
4. Agents: `taste`, `compliance` (and `reach` for polls); apply fixes. Save the file; reply.
