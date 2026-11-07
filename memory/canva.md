# Canva — what we know (read before ANY Canva work; add what you learn after)

Rule: never re-explore Canva from scratch. Read this file, use what works, and append anything new (feature, error,
workaround, good template) to the right section with the date. Update an entry instead of duplicating it.

## Access
- His Canva Pro account ("v sairam"). Use two surfaces together:
  - Canva connector (`mcp__claude_ai_Canva__*`): search/copy/read designs, swap text and media, export.
  - His logged-in Chrome via Claude in Chrome (`mcp__claude-in-chrome__*`): run headless jobs with `claude --chrome`.
- NEVER use Playwright. Its browser has no Canva login.
- Designs stay private. Nothing is shared publicly.

## Connector capabilities (tested 2026-11-07)
- `create-design` cannot make video designs. Start a video by copying an existing video design or template (`copy-design`).
- Template search through the connector only finds **Brand Templates**. Browsing public video templates needs canva.com
  in his Chrome (Templates → Video → Mobile video / YouTube Shorts).
- `perform-editing-operations` can replace text, swap image/video fills and reposition elements.
  It **cannot** add animations or transitions.
  - `update_fill` with a video on a circle shape fails: `not_permitted: "The shape does not contain an editable fill"`.
    Workaround: in the editor, set the video's corner rounding to half its width.
  - `format_text` styles a whole text element; you can't highlight one word inside it.
- Export: MP4 `vertical_1080p`, pro quality. Animations and page transitions are included in the MP4.

## Editor behaviour (tested 2026-11-07)
- Page transitions overlap neighbouring pages, so the design gets shorter (13 × 0.3 s wipes: 46.1 s → 42.1 s) and the voice is
  clipped at each cut. Fix: pad each clip with a freeze frame plus silence as long as the transition, then use Replace (keeps rounding and position).
- Photo Zoom / Photo Flow set to "Both" animates out to the black page background just before a transition (black flash).
  Use "On enter" only.
- Captions show a whole page at once. Phrase timing needs element timing set by hand per caption (slow).
- Uploaded alpha video (WebM/ProRes 4444) plays with a solid background, so no transparent presenter.
- Magic Animate restyles every element, including the presenter and captions. Avoid it on edits.
- Exported MP4 is H.264 **level 5.0**, which fails `pipeline verify`: re-encode to High@4.2.
  The mix is about **-24.8 LUFS**: loudnorm to -14.
- Animations available: element Animate (Photo Zoom, Photo Flow, …), Colour Wipe page transition with direction and
  duration (0.3 s diagonal ↖ in accent yellow is the closest to the Osm Dhruva corner wipe), custom motion paths up to 10 s,
  up to 50 custom animations per design. Animations are kept when the media in a template is replaced.

## Decisions
- 2026-11-07 trial (pressure-cooker, design `DAHaN99mNLs`, https://www.canva.com/d/skL23-KJWdm7gHq). Full-video edits
  in Canva took about 36 min and about 150 fragile clicks, with no word-timed captions and no SFX. The owner chose the **FFmpeg
  compose** as the editor; it takes the Canva touches (diagonal accent wipe, alternating zoom/pan, label pill next to the
  circle). Use Canva for thumbnails, title/end cards and template inspiration.

## Templates (shortlist — fill from canva.com in his Chrome; link, why it fits, which transitions/animations)
- (none reviewed yet)
