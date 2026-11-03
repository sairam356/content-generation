"""Free local renderer (no Higgsfield): your recorded face video + Wav2Lip lip-sync for presenter scenes,
Gemini image generation + ffmpeg zoom/pan for b-roll, picture-in-picture for presenter_overlay scenes.

Needs: tools/Wav2Lip installed by setup/setup-wav2lip.ps1, narration from `pipeline tts`, and
assets/me/video/*.mp4 (20-30 s of you facing the camera, mouth relaxed) or a photo in assets/me/photos.
Writes project/frames/scene_<id>.png, project/clips/scene_<id>.mp4 (+ cta.mp4) and timeline.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import config

W2L_DIR = config.ROOT / "tools" / "Wav2Lip"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
FPS = 25


def _run(cmd: list[str], **kw) -> None:
    r = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if r.returncode != 0:
        sys.exit(f"[render] command failed: {' '.join(str(c) for c in cmd[:4])} ...\n{r.stderr[-2000:]}")


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def w2l_python() -> Path:
    py = W2L_DIR / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists() or not (W2L_DIR / "checkpoints" / "wav2lip_gan.pth").exists():
        sys.exit("[render] Wav2Lip not installed. Run setup\\setup-wav2lip.ps1 (Windows) first.")
    return py


def base_face() -> Path:
    vids = sorted(p for p in (config.ASSETS_DIR / "video").glob("*") if p.suffix.lower() in VIDEO_EXT)
    if vids:
        return vids[0]
    pics = sorted(p for p in (config.ASSETS_DIR / "photos").glob("*") if p.suffix.lower() in IMAGE_EXT)
    if pics:
        print("[render] no assets/me/video/*.mp4 found - using a still photo (less natural). Record a 20-30 s video.")
        return pics[0]
    sys.exit("[render] put a 20-30 s video of yourself in assets/me/video/ (or a photo in assets/me/photos/)")


def wav2lip(face: Path, audio: Path, out: Path, force: bool = False) -> Path:
    if out.exists() and not force:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    resize = config.env("WAV2LIP_RESIZE", "2")
    t0 = time.time()
    cmd = [str(w2l_python()), "inference.py", "--checkpoint_path", "checkpoints/wav2lip_gan.pth",
           "--face", str(face), "--audio", str(audio), "--outfile", str(out),
           "--resize_factor", resize, "--pads", "0", "15", "0", "0",
           "--wav2lip_batch_size", config.env("WAV2LIP_BATCH", "16"), "--face_det_batch_size", "2"]
    if face.suffix.lower() in IMAGE_EXT:
        cmd += ["--fps", str(FPS)]
    _run(cmd, cwd=W2L_DIR)
    print(f"[render]   wav2lip {out.name} ({time.time() - t0:.0f}s)")
    return out


def gemini_image(prompt: str, out: Path, force: bool = False) -> Path:
    if out.exists() and not force:
        return out
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
    models = [m for m in config.env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image,gemini-3-pro-image-preview").split(",") if m]
    full = (f"{prompt}. Vertical 9:16 composition, photorealistic, sharp, high detail, cinematic lighting, "
            "no text, no captions, no watermark, no logos.")
    last = None
    for model in models:
        for attempt in range(3):
            try:
                cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
                try:
                    cfg.image_config = types.ImageConfig(aspect_ratio="9:16")
                except Exception:  # noqa: BLE001 - older SDK without ImageConfig
                    pass
                resp = client.models.generate_content(model=model, contents=full, config=cfg)
                for part in resp.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(part.inline_data.data)
                        return out
                raise RuntimeError("no image in response")
            except Exception as e:  # noqa: BLE001
                last = e
                print(f"[render]   image {model} attempt {attempt + 1} failed: {str(e)[:160]}", file=sys.stderr)
                time.sleep(4 * (attempt + 1))
    sys.exit(f"[render] image generation failed: {last}")


def zoompan(image: Path, out: Path, seconds: float, force: bool = False) -> Path:
    if out.exists() and not force:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = max(int(seconds * FPS), FPS)
    step = 0.25 / frames
    vf = (f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
          f"zoompan=z='min(zoom+{step:.6f},1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={FPS},"
          "format=yuv420p")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-vf", vf, "-frames:v", str(frames),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
    return out


def overlay(background: Path, face_clip: Path, out: Path, force: bool = False) -> Path:
    """Presenter picture-in-picture in the lower-left third (the Osm Dhruva look)."""
    if out.exists() and not force:
        return out
    pos = config.env("OVERLAY_POS", "left")
    x = "40" if pos == "left" else "W-w-40"
    fc = ("[1:v]scale=460:-2:force_original_aspect_ratio=decrease,format=yuva420p[pip];"
          f"[0:v][pip]overlay=x={x}:y=H-h-300:shortest=1,format=yuv420p")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(background), "-i", str(face_clip), "-filter_complex", fc,
          "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(out)])
    return out


def render(project: Path, force: bool = False) -> Path:
    brief = json.loads((project / "brief.json").read_text(encoding="utf-8"))
    script = brief["script"]
    face = base_face()
    clips, frames, build = project / "clips", project / "frames", project / "build"
    for d in (clips, frames, build):
        d.mkdir(exist_ok=True)
    print(f"[render] face source: {face.name}; {len(script['scenes'])} scenes")

    for s in script["scenes"]:
        sid = s["id"]
        audio = project / (s.get("audio_file") or f"audio/scene_{sid}.wav")
        if not audio.exists():
            sys.exit(f"[render] missing {audio}. Run: python -m pipeline tts {project}")
        secs = _duration(audio) or float(s.get("duration_sec", 5))
        out = clips / f"scene_{sid}.mp4"
        kind = s.get("type", "presenter")
        print(f"[render] scene {sid} ({kind}, {secs:.1f}s)")
        if kind == "presenter":
            wav2lip(face, audio, out, force)
            continue
        frame = gemini_image(s.get("image_prompt") or s["visual_prompt"], frames / f"scene_{sid}.png", force)
        bg = zoompan(frame, build / f"bg_{sid}.mp4", secs, force)
        if kind == "broll":
            if force or not out.exists():
                _run(["ffmpeg", "-y", "-v", "error", "-i", str(bg), "-c", "copy", str(out)])
        else:
            talk = wav2lip(face, audio, build / f"talk_{sid}.mp4", force)
            overlay(bg, talk, out, force)

    cta_audio = script.get("cta_audio_file")
    if cta_audio and (project / cta_audio).exists():
        print("[render] cta")
        wav2lip(face, project / cta_audio, clips / "cta.mp4", force)

    tl = project / "timeline.json"
    if not tl.exists():
        from . import assemble
        tl.write_text(json.dumps(assemble.default_timeline(project), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[render] clips ready in {clips}. Next: python -m pipeline assemble {project}")
    return clips
