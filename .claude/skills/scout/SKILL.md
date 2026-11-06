---
name: scout
description: The YouTuber agent's front door. Whenever the owner shares a viral video he came across (any time, from Claude Code / Desktop / mobile), study it - content, format, music, claims - and tell him plainly whether we should make our own version, what the compliance or permission issues are, and the original angle to take. Stores it as a reference.
allowed-tools: Bash, Read, Write, Edit, Glob, Agent, WebSearch, WebFetch
---
Read `.claude/skills/_shared/preamble.md` first. Argument: a YouTube/Shorts URL (other platforms: paste the
transcript/description) + optional note ("saw this, 5M views").

## Done means
- A verdict card in the reply (≤ 20 lines): WHAT it is · WHY it went viral · DO WE MAKE IT? (yes / yes-with-changes /
  no) · OUR ANGLE (one original hook in Telugu) · COMPLIANCE & PERMISSION flags · WHAT TO BORROW / NEVER COPY ·
  NEXT STEP (`/script <angle>` or drop).
- `memory/references.md` entry added (via the `/ref` procedure) when the verdict is yes or yes-with-changes;
  `memory/done.md`'s "declined" list gets a line when no (so it is not re-suggested).

## Steps (think like an experienced YouTuber reviewing a competitor's hit)
1. Get the facts: `python -m pipeline watch <url>` (Gemini) or `python -m pipeline inspect <url>` (meta,
   transcript, frames). Note channel, views/likes if visible, duration, language, music (title in description /
   audible), on-screen text, whether it is the creator's own footage or compiled clips.
2. Why it worked: the hook, the emotion (surprise / humour / outrage / usefulness), the format, the timing.
3. Should WE do it? Judge like a human who knows this channel (`memory/style.md`, `memory/learnings.md`,
   `memory/done.md`): fits our niches? can he say it to camera with credibility? still fresh in a week? can we add
   something (Indian/Telugu angle, a test, an opinion)? not a near-duplicate of something we did?
4. Compliance & permission (run the `compliance` agent, plus your own read of `policy/youtube.md`):
   - copyrighted music/clips in the original → we cannot reuse them (we use our own footage + Audio Library music);
   - claims needing sources (health, money, science) → list what must be verified before scripting;
   - real named people, brands, mocking → how to keep it safe;
   - anything that would be "reused content" if we mirrored it → state what must be original (script, visuals).
5. `taste` + `reach` agents for the angle; then write the verdict card. If yes: offer the exact `/script` line.
