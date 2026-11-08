# Canva — what we know (read before ANY Canva work; add what you learn after)

Rule: never re-explore Canva from scratch. Read this file, use what works, and append anything new (feature, error,
workaround, good template) to the right section with the date. Update an entry instead of duplicating it.

## Access
- His Canva Pro account ("v sairam"). Use two surfaces together:
  - Canva connector (`mcp__claude_ai_Canva__*`): search/copy/read designs, swap text and media, export.
  - His logged-in Chrome via Claude in Chrome (`mcp__claude-in-chrome__*`): run headless jobs with `claude --chrome`.
- NEVER use Playwright. Its browser has no Canva login.
- Template scouting without the editor (2026-11-07): from a canva.com tab, `fetch('/templates/?query=<q>&pricing=FREE|PRO')` returns
  server-rendered HTML with template links (`/templates/E<11-char id>-<slug>/`), so you can search many terms in one JS call.
  `pricing=FREE` and `pricing=PRO` don't overlap, so use them to label a template Free or Pro (a Pro account shows no crown on the pages).
  The search filter panel has Category, **Feature → Animation**, Style, Theme, **Price (Free/Pro)**, Color. Category in the URL does not filter to video, so add
  "youtube shorts" / "reel" / "mobile video" to the query instead.
- The template page has a preview `<video>`. Reloading it with `crossOrigin='anonymous'` allows canvas frame grabs, so you can measure cuts and
  transition lengths and draw a filmstrip overlay to screenshot. The page count and the transition names are not on the public page (only in the editor,
  and opening the editor copies the template).
- Claude in Chrome `browser_batch` with 3 navigate+analyse+screenshot rounds can time out. Use 1-2 templates per batch.
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
- 2026-11-08 **Local file → Canva without the browser:** call `create-upload-url`, then run `curl -X POST -H "Content-Type: application/octet-stream" --data-binary @file <url>`.
  It returns `{"mediaId":"MA..."}`. Each URL works for one upload only.
- 2026-11-08 `remove-background` on an uploaded frame returns a clean transparent cut-out in about 10 s. Crop tight (head + neck) first:
  a phone frame has a straight shirt edge, so hide it under a bar or the page edge.
- 2026-11-08 **Video templates are opaque to the connector:** a copied Shorts/video template reads as page `type: unsupported`, with no element IDs.
  `insert_fill` lands on top with no locator, and `resize-design` flattens every timed element onto one page. For static work (thumbnails), copy the template's
  *look* on a blank design instead. Make a blank design at an exact size in Chrome:
  `https://www.canva.com/design?create=true&width=1080&height=1920&units=px` (the new design ID is in the redirected URL). Its page is `fixed` and fully editable.
- 2026-11-08 Static design editing: `insert_shape` / `insert_fill` always go on top, so add a backdrop rect and then `layer_element: back`
  (the page background color can't be set). The default font renders bold Telugu correctly. `resize-design` 9:16 → 16:9 only scales the layout into the
  middle of a white page, so lay the wide version out again by hand (about 3 calls). `export-design` PNG with an exact width and height, then curl to disk.
- 2026-11-08 **Thumbnail variants:** run `copy-design` on a finished static thumbnail, then insert the new elements. `layer_element: front` on the bar and its text puts them
  back on top, so the new disc and face tuck under the bar. Two variants took about 6 min with 1 browser action.
- 2026-11-08 `position_element` on a **rotated** element lands off target. For a 990x312 text at -3°, the stored `top` came out 25.7 px below the requested value.
  After a move, read the returned `top` and correct by the difference. Big text with lineHeight 1 (260 px in a 312 px box) renders its glyphs low:
  to centre them in a 280 px bar, the stored text `top` is about bar top - 11.

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
- 2026-11-08 Thumbnail test (pressure-cooker, `DAHaUherVyY` 9:16 + `DAHaUluuTw4` 16:9, report `.state/canva_thumb_report.md`). About 8.5 min,
  almost all through the connector. Recipe: dark topic still full-bleed, a tilted yellow pill (black Telugu, 120 px bold), the face cut-out on a yellow disc,
  and a black bar with a yellow border holding the hook number (225 px). Verdict: it beats the FFmpeg face-only thumbnail on topic clarity and contrast.
  Weak spots: a soft, non-Indian AI cooker and a smaller face. Use a sharp, India-specific still and a bigger face disc next time.

## Templates (shortlist — fill from canva.com in his Chrome; link, why it fits, which transitions/animations)
Scouted 2026-11-07: 22 previews opened (21 Free + 1 Pro) from 11 searches. Screenshots (filmstrips of the preview) are in
`.state/canva_templates/<n>-<slug>.png`, grid in `contact.jpg`. "Pages" is estimated from the hard cuts in the preview,
because the exact count only shows inside the editor and opening the editor would copy the template. All 8 are **Free**.
- 2026-11-07 **1. Archeology Facts YouTube Shorts (Educators)**: https://www.canva.com/templates/EAHXf4jrwG0-archeology-facts-youtube-shorts-in-dark-orange-purple-white-style-for-educators/
  Free · 25 s · about 9 pages (a cut every 2.4 s on average). Transitions: hard cuts, plus a 0.2 s flat peach colour flash, after which the
  **split panel slides up** from the bottom. Animations: the title is three stacked pills popping in over a framed presenter, and keyword captions use
  a purple pill with the key word highlighted. Layout: presenter full → **split** (presenter top, rounded-frame visual bottom with an
  orange border) → full-screen B-roll cut-in (Colosseum). Captions sit at the middle of the frame (on his chest). Fit for 46-60 s: **high**,
  because it already alternates the presenter, a split and full B-roll. Steal: the colour flash before the split, the bottom panel sliding up in 0.2 s, and the pill caption with the keyword in an accent colour.
- 2026-11-07 **2. Orange and Cream Bold Myth Busting Fact Check YouTube Shorts**: https://www.canva.com/templates/EAHYqItLJUk-orange-and-cream-bold-myth-busting-fact-check-youtube-shorts/
  Free · 26 s · about 12 pages (a cut every **2.2 s**). Transitions: hard cuts, and the outro is a shape mask (plane window) sliding out over
  0.3 s. Animations: an orange label pill ("MYTH 1" / "FACT") in the centre, red ✗ and green ✓ stickers popping in, a cursor-click
  gimmick, and a small white box growing at a cut. Layout: none (full-screen footage). Fit: **high for pacing** (closest to Osm Dhruva's
  1.5-2.5 s visual cadence). Steal: the MYTH/FACT pill, the ✓/✗ sticker pop (scale 0→110→100 % over about 0.2 s), and a shape-mask outro.
- 2026-11-07 **3. Black and Yellow Unique Facts Explainer YouTube Shorts**: https://www.canva.com/templates/EAHXegpkAG4-black-and-yellow-unique-facts-explainer-youtube-shorts/
  Free · 23 s · about 5 pages. Transitions: hard cuts. On the black grid page, a yellow bar draws across, then text and photo cards **rise in tilted**
  (0.2-0.3 s). Layout: presenter full for the hook and the CTA. Explain pages are two stacked full-width photos (a split of visuals) with a yellow label pill
  on the seam. Fit: **high**: same yellow-on-black accent and the same hook → visuals → CTA spine as our plans. Steal: the yellow bar that draws
  in before the text, the pill on the seam between two stacked visuals, and the tilted photo cards rising in.
- 2026-11-07 **4. News Explainer Mobile Video, Yellow Black White Modern Type**: https://www.canva.com/templates/EAGYSkixKKo-news-explainer-mobile-video-in-yellow-black-and-white-modern-type-style/
  Free · 11 s · about 5 pages (a cut every 1.8 s). Transition: a **vertical slice / blinds wipe, about 0.7 s** (the image breaks into vertical strips that
  slide away), and the text block slides out with it. Animations: a yellow pill title with a white sub-pill, and a black text box at the top for the CTA.
  Layout: none (B&W photos). Fit: medium as a template, **high as a transition source**. Steal: the slice wipe (build it in FFmpeg
  as 6-8 vertical strips with staggered x offsets, shortened to 0.3 s).
- 2026-11-07 **5. Yellow Black Vinyl Music History Explainer YouTube Shorts**: https://www.canva.com/templates/EAHYhLX5Exc-yellow-black-vinyl-music-history-explainer-youtube-shorts/
  Free · 17 s · 5 pages of about 3.5 s. Transitions: a **colour-bar stripe wipe of about 0.5 s** (yellow/white/black bars sweep right to left) and a
  push/slide-in from the right. Animations: monospace typewriter year and fact text. Layout: full-screen footage. Fit: medium (slow
  pages, no presenter). Steal: the striped accent-colour wipe, a punchier cousin of our diagonal accent wipe.
- 2026-11-07 **6. Purple Yellow and Black Modern Podcast Myth vs Fact YouTube Shorts**: https://www.canva.com/templates/EAHWeBuHpMU-purple-yellow-and-black-modern-podcast-myth-vs-fact-youtube-shorts/
  Free · 18 s · 4 cuts between speakers. Transitions: hard cuts. Animations: **word-by-word pop captions** in bold condensed white with
  the **key word in yellow italic**. Captions sit left of centre, at mid height. Layout: presenter full (talking head). Fit: high for caption style.
  Steal: word-pop timing and a single accent-colour keyword per phrase (maps to our `words.json` word timings).
- 2026-11-07 **7. Movie Explainer YouTube Shorts, Cream Light Yellow**: https://www.canva.com/templates/EAHXfdmTQ2Y-movie-explainer-youtube-shorts-in-cream-light-yellow-style-for-entertainment/
  Free · 14 s · 1 page (all motion is element timing). Animations: B-roll **inset cards pop in** (about 0.1 s) over the presenter's chest, and serif
  captions with a soft glow appear word by word. Layout: presenter full + inset card in the lower middle. This is a 5th layout we don't have
  ("card"). Fit: medium-high for quieter explainer beats. Steal: the inset-card layout for beats where his face must stay on screen.
- 2026-11-07 **8. Blue White and Orange Bold Sea Life Random Facts YouTube Shorts**: https://www.canva.com/templates/EAHWaOdOw2g-blue-white-and-orange-bold-sea-life-random-facts-youtube-shorts/
  Free · 18 s · 6 pages (a cut every 2.8 s). Transitions: hard cuts. The big number ("01"…"05") fades in over about 0.5 s and the fact text rises in.
  Layout: none (full-screen photo per fact). Fit: medium (listicle "n facts" videos only). Steal: a big numbered counter in a
  corner for list videos.
- Rejected (static, slow or off-format): Yellow Moody Cinematic Explainer (EAHYglfchUk), Space Facts Educators (EAHXwOF562s,
  but its typewriter phrase captions are nice), Neon AI Facts (EAHYW-JBviU), Black and Blue Breaking News (EAHDbigmgTM), Podcast Clip
  (EAHXHmbx7oQ), Communication Tips Talking Head (EAHZUtoGIgI, which has a nice tilted "TIP 1" pill and doodle arrow), Live Journal Split
  (EAHRlveu6no), Did You Know TikTok (EAGvXz8AUYU), Lets Study Science (EAFqdP8ueRU), Red News Live (EAHYnBOXsPs), Tax Facts
  (EAHXezMgl3g, cut-out halftone presenter), Budgeting Rule (EAHXfRRC5cc, no presenter), Elegant History (EAHZ8G_XGqg), Did You
  Know Random Facts (Pro, EAFqq3DJmL4, illustrated).

**Best 3 for us and why (2026-11-07)**
1. **Archeology Facts (EAHXf4jrwG0)**: the only one that already switches between presenter full, split and full-screen B-roll with pill
   captions, which is our whole format in one template.
2. **Myth Busting Fact Check (EAHYqItLJUk)**: a new full-screen visual every 2.2 s with label pills and ✓/✗ stickers. Use it as the pacing reference.
3. **Unique Facts Explainer (EAHXegpkAG4)**: our yellow-on-black look, a presenter hook and CTA, and stacked visuals with a pill on the seam.
Pattern across all of them: Canva's best Shorts templates use **hard cuts plus element motion** (pill pops, panels sliding in, cards rising in),
not long page transitions. Only #4 and #5 have real wipes (slice 0.7 s, colour stripes 0.5 s). For our FFmpeg editor: keep hard cuts as the default,
add pill/sticker pop-ins, and save wipes for section changes.
