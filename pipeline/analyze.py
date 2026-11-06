"""Step 1: understand a YouTube Short with Gemini and turn it into a Telugu scene-by-scene brief.

Gemini accepts a public YouTube URL directly, so nothing is downloaded. Two calls are made:
  1. analysis  - transcript, concept, structure, visual/animation style, on-screen text
  2. telugu    - an ORIGINAL Telugu script that re-explains the same concept in the user's voice,
                 split into scenes that Higgsfield can render (presenter talking / b-roll)
Output: projects/<slug>/brief.json  (+ brief.md, script_te.txt, claude_prompt.md)
"""
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types

from . import config

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "source_language": {"type": "string"},
        "duration_estimate_sec": {"type": "integer"},
        "transcript_original": {"type": "string"},
        "transcript_english": {"type": "string"},
        "core_concept": {"type": "string", "description": "The single idea the short teaches, 1-2 sentences"},
        "hook": {"type": "string", "description": "How the first 3 seconds grab attention"},
        "structure": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "t_start": {"type": "number"},
                    "t_end": {"type": "number"},
                    "beat": {"type": "string"},
                    "what_is_shown": {"type": "string"},
                    "what_is_said": {"type": "string"},
                },
                "required": ["t_start", "t_end", "beat", "what_is_shown", "what_is_said"],
            },
        },
        "presenter": {
            "type": "object",
            "properties": {
                "on_camera": {"type": "boolean"},
                "framing": {"type": "string"},
                "energy": {"type": "string"},
                "setting": {"type": "string"},
            },
            "required": ["on_camera", "framing", "energy", "setting"],
        },
        "visual_style": {"type": "string"},
        "animation_style": {"type": "string"},
        "on_screen_text": {"type": "array", "items": {"type": "string"}},
        "key_images": {"type": "array", "items": {"type": "string"},
                       "description": "Concrete objects / diagrams / b-roll that carry the explanation"},
        "why_it_works": {"type": "string"},
        "facts_to_verify": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "source_language", "transcript_original", "transcript_english", "core_concept",
                 "hook", "structure", "presenter", "visual_style", "animation_style", "on_screen_text",
                 "key_images", "why_it_works"],
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title_te": {"type": "string"},
        "title_en": {"type": "string"},
        "hook_te": {"type": "string"},
        "total_duration_sec": {"type": "integer"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "type": {"type": "string", "enum": ["presenter", "broll", "presenter_overlay"]},
                    "duration_sec": {"type": "integer", "description": "5 or 10"},
                    "narration_te": {"type": "string", "description": "Telugu script spoken in this scene"},
                    "narration_en": {"type": "string", "description": "English gloss of narration_te"},
                    "delivery": {"type": "string", "description": "voice direction: energy, pace, emotion"},
                    "visual_prompt": {"type": "string",
                                      "description": "English prompt for the video model: setting, action, camera, mood. For presenter scenes describe the presenter's performance and gestures beat by beat."},
                    "on_screen_text_te": {"type": "string"},
                    "image_prompt": {"type": "string",
                                     "description": "English prompt for the still start-frame (9:16) that this scene animates from"},
                },
                "required": ["id", "type", "duration_sec", "narration_te", "narration_en", "delivery",
                             "visual_prompt", "on_screen_text_te", "image_prompt"],
            },
        },
        "cta_te": {"type": "string"},
        "caption_te": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "thumbnail_prompt": {"type": "string"},
    },
    "required": ["title_te", "title_en", "hook_te", "total_duration_sec", "scenes", "cta_te", "caption_te",
                 "hashtags", "thumbnail_prompt"],
}

ANALYSIS_PROMPT = """You are a short-form video analyst. Watch this YouTube Short completely (video AND audio).
Produce a precise, factual breakdown. Transcribe what is actually said (keep the original language) and give
an English translation. Describe the editing: pacing, camera, animation / motion-graphics style, colours,
on-screen text, props, diagrams. Explain the concept being taught and why the short holds attention.
List any factual claims that should be double-checked before re-using them."""

REPLICATE_PROMPT = """You are a Telugu YouTube Shorts script adapter and shot-list director.

Below is a frame-accurate analysis of a reference Short that performed very well. Produce a Telugu REPLICA:
SAME idea, SAME transcript content and order, SAME structure and timing, SAME shot framing, background,
colours, props, pacing and quality. The ONLY changes: the presenter is replaced by the channel owner
(his AI avatar + his cloned voice) and everything spoken is in Telugu.

Rules:
- Scenes: one scene per beat of analysis.structure (merge beats shorter than 3s with their neighbour). Each
  scene duration_sec = that beat's length rounded to 5 or 10 (video models render 5s/10s clips). Keep the
  total close to the reference duration.
- narration_te: faithful natural spoken Telugu of exactly what is said in that beat (same facts, same numbers,
  same order, same jokes). HARD word budget: 5s scene <= 12 Telugu words, 10s scene <= 24 words (Telugu is
  spoken at ~2.3 words/s). If a beat says more than fits, split it into two scenes rather than compressing. Telugu script, not transliteration; keep English technical words in English letters
  the way Telugu speakers say them. Do not add, drop or re-explain content.
- type: "presenter" when the reference shows the presenter talking to camera; "presenter_overlay" when the
  presenter is on screen with a graphic/footage behind or beside him; "broll" when no presenter is visible.
- visual_prompt / image_prompt (ENGLISH, for Higgsfield Soul/Seedance): reproduce what_is_shown exactly -
  framing, camera move, background, lighting, colour palette, props, on-screen objects, motion. For presenter
  scenes always start with "The exact man from the reference image, " then the same framing, position,
  outfit colour, setting and gestures as the original presenter. Vertical 9:16. Never put readable text
  inside the generated video; captions are burned in later.
- on_screen_text_te: Telugu version of the reference on-screen text for that beat (max 4 words) or empty.
- title_te / caption_te / hashtags: Telugu versions of the reference title and caption; cta_te = the
  reference's call to action in Telugu (or a short follow/comment CTA if it had none).
- thumbnail_prompt: the reference's cover image recreated with the same man in the presenter's place.

Reference analysis (JSON):
{analysis}
"""

SCRIPT_PROMPT = """You are a Telugu YouTube Shorts scriptwriter and director.

Below is an analysis of a reference Short. Write an ORIGINAL Telugu Short that teaches the SAME concept
in a fresh way (do not translate the reference line by line; re-explain it, keep the facts correct).

The presenter is a real person (the channel owner) who will appear as an AI avatar of himself, speaking
in his own cloned voice. Write for him:
- Language: natural spoken Telugu (conversational, the way a friend explains), Telugu script (not transliteration).
  Keep common English technical words in English letters inside the Telugu sentence when Telugu speakers
  normally say them that way (e.g. "AI", "battery", "percent").
- Tone: confident, strong, direct, slightly dramatic; hook in the first sentence; one idea per scene;
  short punchy sentences that are easy to lip-sync.
- Total length budget: about {target} seconds of narration. Telugu speaks ~2.3 words/sec; size the
  narration_te of each scene to fit its duration_sec (5 or 10 seconds only; 5s ~ 10-12 words, 10s ~ 20-24 words).
- Channel formula (viral Telugu facts channels like Osm Dhruva): title is a curiosity question
  ("🤯 ఇది ఎలా తయారు చేస్తారు?"), the FIRST sentence is that question, then a fast answer with 3-5 surprising
  facts, then a one-line twist/tip, then CTA. Topics: how things are made, kitchen hacks, animals, body science.
- Scenes: 4 to 8. Prefer "presenter_overlay" scenes: the presenter stands in the lower-left/right third of the
  frame reacting to the topic (surprised, pointing, explaining with hands) while a photorealistic scene of the
  topic fills the frame behind him. Use "broll" (topic visual only, no face) for process shots (machines,
  close-ups, cross-sections) and "presenter" (talking head) only for the hook and the CTA.
- visual_prompt / image_prompt are in ENGLISH for the video model (Higgsfield Seedance / Soul). For presenter and
  presenter_overlay scenes always start with: "The exact man from the reference image, " then where he stands
  in the frame, his expression/gesture beat by beat against the narration, then the background scene in
  photorealistic detail (what the viewer should see about the topic), lighting, camera. Vertical 9:16, locked-off
  or slow push-in, crisp photoreal look. Never put readable text inside the generated video; captions are added later.
- thumbnail_prompt: the same man in the lower corner with a shocked/pointing expression, the most striking
  topic visual behind him, bright and saturated, no text.
- on_screen_text_te: max 4 Telugu words, the key phrase of that scene (or empty).
- End with a CTA scene (follow / comment) in cta_te and write a Telugu caption + hashtags.

Reference analysis (JSON):
{analysis}
"""


def _client() -> genai.Client:
    return genai.Client(api_key=config.require_env("GEMINI_API_KEY"))


def _generate(client: genai.Client, model: str, contents, schema: dict, retries: int = 3) -> dict:
    last = None
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.7,
                ),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 - surface after retries
            last = e
            wait = 5 * (attempt + 1)
            print(f"[gemini] attempt {attempt + 1} failed: {e}. retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    fallback = config.env("GEMINI_FALLBACK_MODEL", "gemini-flash-lite-latest")
    if retries > 2 and fallback and fallback != model:
        print(f"[gemini] {model} unavailable, falling back to {fallback}", file=sys.stderr)
        return _generate(client, fallback, contents, schema, retries=2)
    raise SystemExit(f"[gemini] giving up: {last}")


def analyze_video(url: str, model: str) -> dict:
    client = _client()
    video_part = types.Part(file_data=types.FileData(file_uri=url, mime_type="video/*"))
    return _generate(client, model, [video_part, ANALYSIS_PROMPT], ANALYSIS_SCHEMA)


WORDS_PER_SEC = 2.3          # measured Telugu narration speed
MAX_SCENE_WORDS = 24         # one 10s clip


def reference_duration(url: str) -> int | None:
    """Real length of the reference Short (yt-dlp metadata) so the Telugu script keeps the same pacing."""
    import subprocess
    import sys as _sys
    for cmd in (["yt-dlp"], [_sys.executable, "-m", "yt_dlp"]):
        try:
            r = subprocess.run(cmd + ["--no-warnings", "--print", "duration", url], capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                return int(float(r.stdout.strip().splitlines()[-1]))
        except Exception:  # noqa: BLE001
            continue
    return None


def split_long_scenes(scenes: list[dict]) -> list[dict]:
    """Gemini regularly ignores the word budget. Split any scene longer than one 10s clip into several
    consecutive scenes (same type/visual) at sentence/clause boundaries so every b-roll image lasts <= ~10s."""
    out: list[dict] = []
    for s in scenes:
        words = s["narration_te"].split()
        if len(words) <= MAX_SCENE_WORDS + 2:
            out.append(s)
            continue
        parts = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|(?<=,)\s+", s["narration_te"]) if x.strip()]
        chunks, cur = [], ""
        for part in parts:
            if cur and len((cur + " " + part).split()) > MAX_SCENE_WORDS:
                chunks.append(cur)
                cur = part
            else:
                cur = (cur + " " + part).strip()
        if cur:
            chunks.append(cur)
        final = []
        for c in chunks:  # hard cap: a single run-on sentence is cut by words
            w = c.split()
            while len(w) > MAX_SCENE_WORDS + 4:
                final.append(" ".join(w[:MAX_SCENE_WORDS])); w = w[MAX_SCENE_WORDS:]
            final.append(" ".join(w))
        for i, c in enumerate(final):
            n = dict(s)
            n["narration_te"] = c
            n["duration_sec"] = 5 if len(c.split()) <= 12 else 10
            if i:
                n["on_screen_text_te"] = ""
                n["image_prompt"] = (s.get("image_prompt") or s.get("visual_prompt", "")) + f" (alternate angle {i + 1}, same scene, same colours)"
                n["narration_en"] = ""
            out.append(n)
    for i, s in enumerate(out, 1):
        s["id"] = i
    return out


def write_telugu_script(analysis: dict, model: str, target_sec: int, mode: str = "replicate") -> dict:
    client = _client()
    tmpl = REPLICATE_PROMPT if mode == "replicate" else SCRIPT_PROMPT
    prompt = tmpl.format(target=target_sec, analysis=json.dumps(analysis, ensure_ascii=False, indent=1))
    script = _generate(client, model, prompt, SCRIPT_SCHEMA)
    for s in script["scenes"]:
        s["duration_sec"] = 10 if s.get("duration_sec", 5) > 5 else 5
    before = len(script["scenes"])
    script["scenes"] = split_long_scenes(script["scenes"])
    if len(script["scenes"]) != before:
        print(f"[analyze] split {before} -> {len(script['scenes'])} scenes to respect the 10s clip budget")
    script["total_duration_sec"] = int(sum(len(s["narration_te"].split()) for s in script["scenes"]) / WORDS_PER_SEC)
    return script


def render_markdown(brief: dict) -> str:
    a, s = brief["analysis"], brief["script"]
    lines = [
        f"# {s['title_te']}  ({s['title_en']})",
        "",
        f"Source: {brief['source_url']}",
        f"Concept: {a['core_concept']}",
        f"Reference hook: {a['hook']}",
        f"Reference style: {a['visual_style']} | animation: {a['animation_style']}",
        "",
        "## Telugu script",
        "",
    ]
    for sc in s["scenes"]:
        lines += [
            f"### Scene {sc['id']} - {sc['type']} - {sc['duration_sec']}s",
            f"**TE:** {sc['narration_te']}",
            f"**EN:** {sc['narration_en']}",
            f"Delivery: {sc['delivery']}",
            f"Visual: {sc['visual_prompt']}",
            f"Start frame: {sc['image_prompt']}",
            f"On-screen: {sc['on_screen_text_te'] or '-'}",
            "",
        ]
    lines += ["## CTA", s["cta_te"], "", "## Caption", s["caption_te"], " ".join(s["hashtags"]), "",
              "## Facts to verify"] + [f"- {f}" for f in a.get("facts_to_verify", [])]
    return "\n".join(lines) + "\n"


CLAUDE_PROMPT = """Make the Telugu Short for project `{project}`.

Read `{project}/brief.json`. Narration audio for every scene is in `{project}/audio/scene_<id>.wav`
(already in my cloned voice, Telugu). My face photos are in `assets/me/photos`.

Follow the `/make-short` workflow in CLAUDE.md:
1. Make sure a Soul ID of me exists (HIGGSFIELD_SOUL_ID in .env, else train one from assets/me/photos).
2. For every scene generate a 9:16 start frame (presenter scenes use my Soul ID), then the clip:
   presenter scenes = Seedance 2.5 with the scene audio as audio reference (lip-sync), b-roll = image-to-video.
3. Download clips to `{project}/clips/scene_<id>.mp4`, write `{project}/timeline.json`,
   then run `python -m pipeline assemble {project}`.
Show me the cost estimate before the first paid generation.
"""


def run(url: str, name: str | None = None, target_sec: int | None = None, mode: str | None = None) -> Path:
    model = config.env("GEMINI_MODEL", "gemini-flash-latest")
    ref_sec = reference_duration(url)
    if not target_sec:
        target_sec = ref_sec or int(config.env("TARGET_DURATION_SEC", "45"))
    print(f"[analyze] reference length: {ref_sec or '?'}s -> narration budget {target_sec}s")
    mode = mode or config.env("SCRIPT_MODE", "replicate")
    vid = config.youtube_id(url)
    print(f"[analyze] watching {url} with {model} ...")
    analysis = analyze_video(url, model)
    analysis["duration_sec"] = ref_sec
    print(f"[analyze] concept: {analysis['core_concept']}")
    print(f"[analyze] writing Telugu script ({mode}) ...")
    script = write_telugu_script(analysis, model, target_sec, mode)

    slug = name or f"{date.today():%Y%m%d}-{config.slugify(script['title_en'])}-{vid}"
    out = config.PROJECTS_DIR / slug
    (out / "audio").mkdir(parents=True, exist_ok=True)
    (out / "frames").mkdir(exist_ok=True)
    (out / "clips").mkdir(exist_ok=True)

    brief = {
        "project": slug,
        "source_url": url,
        "source_video_id": vid,
        "created": date.today().isoformat(),
        "model": model,
        "mode": mode,
        "analysis": analysis,
        "script": script,
    }
    (out / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "brief.md").write_text(render_markdown(brief), encoding="utf-8")
    (out / "script_te.txt").write_text(
        "\n\n".join(f"[{s['id']}] {s['narration_te']}" for s in script["scenes"]) + f"\n\n[CTA] {script['cta_te']}\n",
        encoding="utf-8")
    rel = f"projects/{slug}"
    (out / "claude_prompt.md").write_text(CLAUDE_PROMPT.format(project=rel), encoding="utf-8")
    print(f"[analyze] brief written to {out}")
    return out
