"""Step 2: your voice, in Telugu, with a strong broadcast presence (ElevenLabs + ffmpeg).

  clone   - Instant Voice Clone from assets/me/voice/*.wav|mp3  -> ELEVENLABS_VOICE_ID saved to .env
  design  - (optional) ElevenLabs Voice Design: a deep, authoritative presenter voice to compare against your clone
  tts     - one narration file per scene with eleven_v4 (language te) + mastering preset -> project/audio/scene_<id>.wav
  preview - speak one Telugu line to check the voice before spending credits on a full project
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from . import config

API = "https://api.elevenlabs.io/v1"

# Settings tuned for an authoritative explainer voice. stability 0.5 ("Natural") is the middle setting
# that v3/v4 accept; similarity high so it stays *your* voice; a little style for punch.
VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.85,
    "style": 0.35,
    "use_speaker_boost": True,
    "speed": 1.0,
}

# ffmpeg mastering chains. "deep" = broadcast presenter: gentle low-end lift (chest), presence bump,
# compression for consistent loudness, limiter, then normalise to -14 LUFS (YouTube's target).
ENHANCE_PRESETS = {
    "deep": (
        "highpass=f=65,"
        "equalizer=f=110:t=q:w=1.1:g=4,"
        "equalizer=f=220:t=q:w=1.3:g=1.5,"
        "equalizer=f=400:t=q:w=1.5:g=-1.5,"
        "equalizer=f=3000:t=q:w=1.2:g=2,"
        "acompressor=threshold=-20dB:ratio=3.2:attack=8:release=140:makeup=5,"
        "alimiter=limit=0.93,"
        "loudnorm=I=-14:TP=-1.5:LRA=8"
    ),
    "clean": (
        "highpass=f=80,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=150:makeup=3,"
        "loudnorm=I=-14:TP=-1.5:LRA=9"
    ),
    "none": None,
}


def _headers() -> dict:
    return {"xi-api-key": config.require_env("ELEVENLABS_API_KEY")}


def _save_env(key: str, value: str) -> None:
    env_path = config.ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            found = True
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[voice] saved {key} to .env")


def clone(name: str = "me") -> str:
    samples = sorted(p for p in (config.ASSETS_DIR / "voice").glob("*") if p.suffix.lower() in {".wav", ".mp3", ".m4a"})
    if not samples:
        sys.exit("[voice] put 1-3 recordings (1-3 minutes total, quiet room, your normal Telugu speaking voice) "
                 "in assets/me/voice/ as .wav or .mp3")
    files = [("files", (p.name, p.open("rb"), "audio/mpeg" if p.suffix == ".mp3" else "audio/wav")) for p in samples]
    data = {
        "name": name,
        "description": "Telugu YouTube presenter - cloned from own recordings",
        "labels": json.dumps({"language": "te", "use_case": "narration"}),
        "remove_background_noise": "true",
    }
    print(f"[voice] cloning from {len(samples)} sample(s) ...")
    r = requests.post(f"{API}/voices/add", headers=_headers(), data=data, files=files, timeout=300)
    if r.status_code >= 400:
        sys.exit(f"[voice] clone failed {r.status_code}: {r.text}")
    voice_id = r.json()["voice_id"]
    _save_env("ELEVENLABS_VOICE_ID", voice_id)
    return voice_id


def design(description: str | None = None, sample_text: str | None = None) -> None:
    """Preview 3 designed voices; pick one with `--pick N` to save it as an alternative presenter voice."""
    description = description or (
        "Deep, resonant male voice in his early 30s, Indian (Telugu) speaker, warm chest tone with a strong low "
        "end, confident and authoritative like a news anchor, clear articulation, energetic but controlled, "
        "studio quality"
    )
    sample_text = sample_text or (
        "ఈ ఒక్క విషయం తెలుసుకుంటే మీ జీవితం మారిపోతుంది. చివరి వరకు చూడండి, ఎందుకంటే చాలా మంది ఈ తప్పు చేస్తున్నారు. "
        "ఇప్పుడు నేను చెప్పేది జాగ్రత్తగా వినండి."
    )
    body = {"voice_description": description, "text": sample_text, "model_id": "eleven_ttv_v3"}
    r = requests.post(f"{API}/text-to-voice/design", headers={**_headers(), "Content-Type": "application/json"},
                      json=body, timeout=300)
    if r.status_code >= 400:
        sys.exit(f"[voice] design failed {r.status_code}: {r.text}")
    previews = r.json()["previews"]
    out = config.STATE_DIR / "voice_design"
    out.mkdir(parents=True, exist_ok=True)
    import base64
    meta = []
    for i, p in enumerate(previews, 1):
        path = out / f"preview_{i}.mp3"
        path.write_bytes(base64.b64decode(p["audio_base_64"]))
        meta.append({"n": i, "generated_voice_id": p["generated_voice_id"], "file": str(path)})
        print(f"[voice] preview {i}: {path}")
    (out / "previews.json").write_text(json.dumps({"description": description, "text": sample_text, "previews": meta},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print("[voice] listen, then:  python -m pipeline voice design-save <n>")


def design_save(n: int, name: str = "presenter-deep") -> str:
    meta = json.loads((config.STATE_DIR / "voice_design" / "previews.json").read_text(encoding="utf-8"))
    chosen = next(p for p in meta["previews"] if p["n"] == n)
    body = {"voice_name": name, "voice_description": meta["description"],
            "generated_voice_id": chosen["generated_voice_id"]}
    r = requests.post(f"{API}/text-to-voice", headers={**_headers(), "Content-Type": "application/json"},
                      json=body, timeout=120)
    if r.status_code >= 400:
        sys.exit(f"[voice] save failed {r.status_code}: {r.text}")
    voice_id = r.json()["voice_id"]
    _save_env("ELEVENLABS_ALT_VOICE_ID", voice_id)
    print("[voice] use it with:  python -m pipeline tts <project> --voice-id", voice_id)
    return voice_id


def synthesize(text: str, out_wav: Path, voice_id: str | None = None, model: str | None = None,
               preset: str | None = None, previous_text: str | None = None, next_text: str | None = None) -> Path:
    voice_id = voice_id or config.require_env("ELEVENLABS_VOICE_ID")
    model = model or config.env("ELEVENLABS_MODEL", "eleven_v4")
    preset = preset or config.env("VOICE_ENHANCE_PRESET", "deep")
    body = {
        "text": text,
        "model_id": model,
        "language_code": "te",
        "voice_settings": VOICE_SETTINGS,
        "previous_text": previous_text,
        "next_text": next_text,
    }
    r = requests.post(f"{API}/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                      headers={**_headers(), "Content-Type": "application/json"}, json=body, timeout=300)
    if r.status_code >= 400:
        sys.exit(f"[voice] tts failed {r.status_code}: {r.text}")
    raw = out_wav.with_suffix(".raw.mp3")
    raw.write_bytes(r.content)
    enhance(raw, out_wav, preset)
    return out_wav


def enhance(src: Path, dst: Path, preset: str = "deep") -> Path:
    chain = ENHANCE_PRESETS.get(preset)
    if not shutil.which("ffmpeg"):
        sys.exit("[voice] ffmpeg not found on PATH (setup/setup-windows.ps1 installs it)")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if chain:
        cmd += ["-af", chain]
    cmd += ["-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    subprocess.run(cmd, check=True)
    return dst


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def tts_project(project: Path, voice_id: str | None = None, preset: str | None = None, force: bool = False) -> None:
    brief = json.loads((project / "brief.json").read_text(encoding="utf-8"))
    scenes = brief["script"]["scenes"]
    audio_dir = project / "audio"
    audio_dir.mkdir(exist_ok=True)
    texts = [s["narration_te"] for s in scenes]
    for i, scene in enumerate(scenes):
        out = audio_dir / f"scene_{scene['id']}.wav"
        if out.exists() and not force:
            print(f"[voice] scene {scene['id']}: exists, skipping")
        else:
            print(f"[voice] scene {scene['id']}: {scene['narration_te'][:40]}...")
            synthesize(scene["narration_te"], out, voice_id=voice_id, preset=preset,
                       previous_text=texts[i - 1] if i else None,
                       next_text=texts[i + 1] if i + 1 < len(texts) else None)
        secs = duration(out)
        scene["audio_file"] = f"audio/{out.name}"
        scene["audio_duration_sec"] = round(secs, 2)
        # Video models render 5 or 10 second clips; pick the smallest that covers the narration.
        scene["clip_duration_sec"] = 5 if secs <= 4.6 else 10
        if secs > 10.5:
            print(f"[voice]   WARNING scene {scene['id']} narration is {secs:.1f}s (>10s). "
                  f"Shorten narration_te in brief.json and re-run with --force, or the clip will be padded.")
    cta = brief["script"].get("cta_te")
    if cta:
        out = audio_dir / "cta.wav"
        if not out.exists() or force:
            synthesize(cta, out, voice_id=voice_id, preset=preset)
        brief["script"]["cta_audio_file"] = f"audio/{out.name}"
        brief["script"]["cta_audio_duration_sec"] = round(duration(out), 2)
    (project / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(s["audio_duration_sec"] for s in scenes)
    print(f"[voice] done. {len(scenes)} scenes, {total:.1f}s narration -> {audio_dir}")


def preview(text: str | None = None, voice_id: str | None = None, preset: str | None = None) -> Path:
    text = text or "హలో ఫ్రెండ్స్! ఈ రోజు మనం ఒక అద్భుతమైన విషయం గురించి మాట్లాడుకుందాం. చివరి వరకు చూడండి."
    config.STATE_DIR.mkdir(exist_ok=True)
    out = config.STATE_DIR / "preview.wav"
    synthesize(text, out, voice_id=voice_id, preset=preset)
    print(f"[voice] preview -> {out}")
    return out
