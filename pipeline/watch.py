"""Gemini watches a YouTube Short (public URL, nothing downloaded) and returns a structured analysis.
Used by /ref. If Gemini refuses (quota, 403, private video), /ref falls back to `pipeline inspect`."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from . import config

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "source_language": {"type": "string"},
        "duration_estimate_sec": {"type": "integer"},
        "transcript_original": {"type": "string"},
        "transcript_english": {"type": "string"},
        "core_concept": {"type": "string"},
        "hook": {"type": "string", "description": "What the first 3 seconds do to grab attention"},
        "structure": {"type": "array", "items": {"type": "object", "properties": {
            "t_start": {"type": "number"}, "t_end": {"type": "number"}, "beat": {"type": "string"},
            "what_is_shown": {"type": "string"}, "what_is_said": {"type": "string"}},
            "required": ["t_start", "t_end", "beat", "what_is_shown", "what_is_said"]}},
        "presenter": {"type": "object", "properties": {
            "on_camera": {"type": "boolean"}, "framing": {"type": "string", "description": "where in the frame, how big, what is behind"},
            "energy": {"type": "string"}, "setting": {"type": "string"}},
            "required": ["on_camera", "framing", "energy", "setting"]},
        "layout": {"type": "string", "description": "corner | circle-top | split | full | other - how presenter and visuals share the frame"},
        "visual_style": {"type": "string"},
        "animation_style": {"type": "string"},
        "colours": {"type": "string"},
        "caption_style": {"type": "string"},
        "music_sfx": {"type": "string"},
        "cuts_per_10s": {"type": "number"},
        "on_screen_text": {"type": "array", "items": {"type": "string"}},
        "why_it_works": {"type": "string"},
        "facts_to_verify": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "source_language", "transcript_original", "transcript_english", "core_concept", "hook",
                 "structure", "presenter", "layout", "visual_style", "animation_style", "colours", "caption_style",
                 "why_it_works"],
}

PROMPT = """You are a short-form video analyst. Watch this YouTube Short completely (video AND audio).
Give a precise, factual breakdown: transcript in the original language + English, the beats with timings,
exactly how the presenter and the visuals share the frame (layout), background/animation style, colours,
caption style, music, pacing, and why it holds attention. List claims that should be fact-checked."""


def watch(url: str) -> Path:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
    models = [m for m in config.env("GEMINI_MODEL", "gemini-flash-latest,gemini-flash-lite-latest").split(",") if m]
    part = types.Part(file_data=types.FileData(file_uri=url, mime_type="video/*"))
    last = None
    for model in models:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model, contents=[part, PROMPT],
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=SCHEMA,
                                                       temperature=0.3))
                data = json.loads(resp.text)
                out = config.STATE_DIR / "refs" / config.youtube_id(url)
                out.mkdir(parents=True, exist_ok=True)
                data["url"] = url
                data["model"] = model
                (out / "analysis.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"[watch] {model}: {data.get('title')} ({data.get('duration_estimate_sec')}s, layout={data.get('layout')})")
                print(out / "analysis.json")
                return out / "analysis.json"
            except Exception as e:  # noqa: BLE001
                last = e
                print(f"[watch] {model} attempt {attempt + 1} failed: {str(e)[:200]}", file=sys.stderr)
                time.sleep(4)
    sys.exit(f"[watch] Gemini could not watch the video: {last}\n[watch] use: python -m pipeline inspect {url}")
