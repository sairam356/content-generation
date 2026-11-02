"""Step 1: understand a YouTube Short with Gemini and turn it into a Telugu scene-by-scene brief.

Gemini accepts a public YouTube URL directly, so nothing is downloaded. Two calls are made:
  1. analysis  - transcript, concept, structure, visual/animation style, on-screen text
  2. telugu    - an ORIGINAL Telugu script that re-explains the same concept in the user's voice,
                 split into scenes that Higgsfield can render (presenter talking / b-roll)
Output: projects/<slug>/brief.json  (+ brief.md, script_te.txt, claude_prompt.md)
"""
import json
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
- Scenes: 4 to 8. Alternate "presenter" scenes (he talks to camera) with "broll" scenes (animated
  visual that explains, no face) where the reference used visuals/animation. Use "presenter_overlay" when
  he talks while a graphic/text overlays.
- visual_prompt / image_prompt are in ENGLISH for the video model (Higgsfield Seedance / Soul). For presenter
  scenes always start with: "The exact man from the reference image, " then framing, setting, lighting, and
  the performance written beat by beat against the narration. Vertical 9:16, locked-off or slow push-in,
  phone-video realism. Never put readable text inside the generated video; on-screen text is added later.
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
    raise SystemExit(f"[gemini] giving up: {last}")


def analyze_video(url: str, model: str) -> dict:
    client = _client()
    video_part = types.Part(file_data=types.FileData(file_uri=url, mime_type="video/*"))
    return _generate(client, model, [video_part, ANALYSIS_PROMPT], ANALYSIS_SCHEMA)


def write_telugu_script(analysis: dict, model: str, target_sec: int) -> dict:
    client = _client()
    prompt = SCRIPT_PROMPT.format(target=target_sec, analysis=json.dumps(analysis, ensure_ascii=False, indent=1))
    script = _generate(client, model, prompt, SCRIPT_SCHEMA)
    for s in script["scenes"]:
        s["duration_sec"] = 10 if s.get("duration_sec", 5) > 5 else 5
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


def run(url: str, name: str | None = None, target_sec: int | None = None) -> Path:
    model = config.env("GEMINI_MODEL", "gemini-flash-latest")
    target_sec = target_sec or int(config.env("TARGET_DURATION_SEC", "45"))
    vid = config.youtube_id(url)
    print(f"[analyze] watching {url} with {model} ...")
    analysis = analyze_video(url, model)
    print(f"[analyze] concept: {analysis['core_concept']}")
    print("[analyze] writing Telugu script ...")
    script = write_telugu_script(analysis, model, target_sec)

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
