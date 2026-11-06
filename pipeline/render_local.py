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
           "--face", str(face.resolve()), "--audio", str(audio.resolve()), "--outfile", str(out.resolve()),
           "--resize_factor", resize, "--pads", "0", "15", "0", "0",
           "--wav2lip_batch_size", config.env("WAV2LIP_BATCH", "16"), "--face_det_batch_size", "2"]
    if face.suffix.lower() in IMAGE_EXT:
        cmd += ["--fps", str(FPS)]
    _run(cmd, cwd=W2L_DIR)
    print(f"[render]   wav2lip {out.name} ({time.time() - t0:.0f}s)")
    return out


def _pollinations_image(prompt: str, out: Path) -> Path | None:
    """Free, key-less fallback (Flux via pollinations.ai) when Gemini image models are unavailable."""
    import urllib.parse
    import requests
    q = urllib.parse.quote(prompt[:900])
    for attempt in range(6):
        try:
            r = requests.get(f"https://image.pollinations.ai/prompt/{q}",
                             params={"width": 1080, "height": 1920, "nologo": "true", "model": "flux",
                                     "seed": 11 + attempt}, timeout=180)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                out.parent.mkdir(parents=True, exist_ok=True)
                raw = out.with_suffix(".raw.jpg")
                raw.write_bytes(r.content)
                # crop the service's bottom-right watermark strip, then back to 1080x1920
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-vf",
                                "crop=iw:ih*0.93:0:0,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                                str(out)], check=True)
                raw.unlink(missing_ok=True)
                return out
            print(f"[render]   pollinations attempt {attempt + 1}: HTTP {r.status_code}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[render]   pollinations attempt {attempt + 1} failed: {str(e)[:160]}", file=sys.stderr)
        time.sleep(15 * (attempt + 1))  # anonymous tier is rate-limited (402/429): back off
    return None


def _reference_frame(brief: dict, scene: dict, out: Path) -> Path | None:
    """Last resort: grab the matching frame from the reference Short itself (replicate mode).
    Note: this reuses the reference's footage - OK for a private test, check rights before publishing."""
    url = brief.get("source_url")
    if not url:
        return None
    project = out.parent.parent
    ref = project / "reference.mp4"
    if not ref.exists():
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "-f", "bv*[height<=1920]+ba/b", "--merge-output-format", "mp4",
                            "-o", str(ref), url], capture_output=True, text=True)
        if r.returncode != 0 or not ref.exists():
            print(f"[render]   reference download failed: {r.stderr.strip()[:200]}", file=sys.stderr)
            return None
    start = 0.0
    for sc in brief["script"]["scenes"]:
        if sc["id"] == scene["id"]:
            break
        start += float(sc.get("audio_duration_sec") or sc.get("duration_sec") or 5)
    at = start + min(1.0, float(scene.get("duration_sec", 5)) / 3)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(ref), "-frames:v", "1",
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", str(out)],
                       capture_output=True, text=True)
    if r.returncode == 0 and out.exists():
        print(f"[render]   using reference frame @{at:.1f}s", file=sys.stderr)
        return out
    return None


def gemini_image(prompt: str, out: Path, force: bool = False, brief: dict | None = None, scene: dict | None = None) -> Path:
    if out.exists() and not force:
        return out
    if scene and scene.get("type") == "presenter_overlay":
        prompt = ("Full-frame shot of the topic only (the presenter is composited separately, so NO person, NO face, "
                  "no split-screen): " + prompt)
    full = (f"{prompt}. Vertical 9:16 composition, photorealistic, sharp, high detail, cinematic lighting, "
            "no text, no captions, no watermark, no logos, no close-up human faces.")
    provider = config.env("IMAGE_PROVIDER", "elevenlabs" if config.env("ELEVENLABS_API_KEY") else "gemini").lower()
    last = None
    if provider == "elevenlabs":
        from . import xi_media
        try:
            return xi_media.generate_image(full, out)
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[render]   {e} - falling back", file=sys.stderr)
    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=config.require_env("GEMINI_API_KEY"))
        models = [m for m in config.env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image,gemini-3-pro-image-preview").split(",") if m]
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
                    msg = str(e)
                    print(f"[render]   image {model} attempt {attempt + 1} failed: {msg[:160]}", file=sys.stderr)
                    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                        break  # quota (free tier has 0 image quota): don't burn time retrying
                    time.sleep(4 * (attempt + 1))
        print("[render]   Gemini images unavailable (set IMAGE_PROVIDER=pollinations to skip) - using free pollinations.ai",
              file=sys.stderr)
    if provider != "reference":
        got = _pollinations_image(full, out)
        if got:
            return got
    if brief is not None and scene is not None:
        got = _reference_frame(brief, scene, out)
        if got:
            return got
    sys.exit(f"[render] image generation failed: {last}")


def fit_clip(src: Path, out: Path, seconds: float, force: bool = False) -> Path:
    """Loop/trim a generated clip to the narration length, normalised to 1080x1920@FPS, no audio."""
    if out.exists() and not force:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{seconds:.3f}", "-an",
          "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS},format=yuv420p",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
    return out


def xi_broll(scene: dict, seconds: float, out: Path, force: bool = False) -> Path | None:
    """Real AI video b-roll (Veo via the ElevenLabs flows API). Returns None if generation fails."""
    from . import xi_media
    raw = out.with_name(out.stem + "_raw.mp4")
    if force or not raw.exists():
        prompt = scene.get("visual_prompt") or scene.get("image_prompt") or ""
        if scene.get("type") == "presenter_overlay":
            prompt = "Topic footage only, no presenter, no person talking to camera, no split-screen: " + prompt
        prompt += (". Vertical 9:16 phone-video framing, photorealistic, sharp, cinematic lighting, smooth camera move, "
                   "no on-screen text, no captions, no subtitles, no watermark, no logos.")
        try:
            xi_media.generate_video(prompt, raw)
        except Exception as e:  # noqa: BLE001
            print(f"[render]   {e} - falling back to image b-roll", file=sys.stderr)
            return None
    return fit_clip(raw, out, seconds, force)


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


def face_still(face: Path, out: Path) -> Path:
    """One clean frame of the owner (from assets/me/video or a photo) for image-driven talking-head models."""
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    src = ["-ss", config.env("FACE_STILL_SEC", "1.0"), "-i", str(face)] if face.suffix.lower() in VIDEO_EXT else ["-i", str(face)]
    _run(["ffmpeg", "-y", "-v", "error", *src, "-frames:v", "1", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", str(out)])
    return out


def talking(face: Path, audio: Path, out: Path, force: bool = False) -> Path:
    """Lip-synced presenter clip: ElevenLabs creatify-aurora (sharp, credits) by default when the key is set,
    else / on failure local Wav2Lip (free, CPU)."""
    if out.exists() and not force:
        return out
    provider = config.env("PRESENTER_PROVIDER", "elevenlabs" if config.env("ELEVENLABS_API_KEY") else "wav2lip").lower()
    if provider == "elevenlabs":
        from . import xi_media
        raw = out.with_name(out.stem + "_xi.mp4")
        try:
            t0 = time.time()
            if force or not raw.exists():
                xi_media.generate_talking(face_still(face, out.parent / "face_still.png"), audio, raw)
            _run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-i", str(audio), "-map", "0:v", "-map", "1:a",
                  "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps={FPS},format=yuv420p",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)])
            print(f"[render]   elevenlabs talking {out.name} ({time.time() - t0:.0f}s)")
            return out
        except Exception as e:  # noqa: BLE001
            print(f"[render]   {e} - falling back to Wav2Lip", file=sys.stderr)
    return wav2lip(face, audio, out, force)


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
    video_provider = config.env("VIDEO_PROVIDER", "elevenlabs" if config.env("ELEVENLABS_API_KEY") else "none").lower()
    print(f"[render] face source: {face.name}; {len(script['scenes'])} scenes; b-roll video: {video_provider}")

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
            talking(face, audio, out, force)
            continue
        bg = xi_broll(s, secs, build / f"bg_{sid}.mp4", force) if video_provider == "elevenlabs" else None
        if bg is None:
            frame = gemini_image(s.get("image_prompt") or s["visual_prompt"], frames / f"scene_{sid}.png", force, brief, s)
            bg = zoompan(frame, build / f"bg_{sid}.mp4", secs, force)
        if kind == "broll":
            if force or not out.exists():
                _run(["ffmpeg", "-y", "-v", "error", "-i", str(bg), "-c", "copy", str(out)])
        else:
            talk = talking(face, audio, build / f"talk_{sid}.mp4", force)
            overlay(bg, talk, out, force)

    cta_audio = script.get("cta_audio_file")
    if cta_audio and (project / cta_audio).exists():
        print("[render] cta")
        talking(face, project / cta_audio, clips / "cta.mp4", force)

    tl = project / "timeline.json"
    if not tl.exists():
        from . import assemble
        tl.write_text(json.dumps(assemble.default_timeline(project), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[render] clips ready in {clips}. Next: python -m pipeline assemble {project}")
    return clips
