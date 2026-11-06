---
description: Write an original Telugu Short script (hook -> beats -> CTA) + teleprompter for a topic
argument-hint: <topic or idea> [--style <channel>] [--sec 45-60]
allowed-tools: Bash, Read, Write, Edit, WebSearch, WebFetch
---

Topic: `$ARGUMENTS`

1. `Read memory/style.md` (owner's voice, do/don't, layout preferences) and `Read memory/references.md`
   (formats that work). Match the style of the channel named with --style if any.
2. Verify the facts with WebSearch (2-4 sources, prefer official/Indian sources); keep source URLs.
3. Write the script in NATURAL SPOKEN TELUGU (Telugu script; keep common English words in English letters the
   way Telugu speakers say them: "AI", "battery", "percent"). Target 45-60 s unless --sec says otherwise:
   Telugu speaks ~2.3 words/s, so ~110-140 words total.
   - hook_te: ONE sentence, a curiosity question or shocking claim, max 12 words, says the topic.
   - 4-6 beats: one idea each, 15-30 words, punchy sentences, a surprise/number in at least 3 beats, the last beat
     is a twist, tip or "what this means for you".
   - cta_te: short follow/comment prompt that asks a question back (comments = reach).
   - Per beat also give: broll_prompt (ENGLISH, concrete, what should animate BEHIND the presenter: scene, objects,
     motion, lighting; no text, no people's faces; match references' visual style), label_te (2-4 Telugu words
     for the top label), delivery (how to say it: pace, face, gesture).
   - title_te (with one emoji like 🤯 if the style uses it), description_te (2 lines + question), hashtags
     (8-12, Telugu + English), thumbnail_idea.
4. Save `script.json` with this exact shape:
   {"topic":"...","style_channel":"...","category":"...","title_te":"...","hook_te":"...",
    "beats":[{"id":1,"text_te":"...","broll_prompt":"...","label_te":"...","delivery":"..."}],
    "cta_te":"...","description_te":"...","hashtags":["#..."],"thumbnail_idea":"...","sources":["url"],
    "est_sec":52}
   Folder: the one given, else `topics/<today>/<nn>-<slug>/`. Also write `script.md` (readable) and run
   `python -m pipeline teleprompter <folder>/script.json`.
5. Self-review before saving: hook in <=2 s? every beat earns its place? numbers correct per sources? total words
   within budget? spoken Telugu, not written/literary Telugu? Fix, then reply with hook + beats in 6 lines.
