"""ElevenLabs content-generation ("flows") API: images and short video clips billed to the owner's ElevenLabs credits.

POST /v1/flows/image  {model_id, prompt, aspect_ratio[, images]}            -> {id, status}
POST /v1/flows/video  {model_id, prompt, aspect_ratio, resolution[, images, generate_audio]}
GET  /v1/flows/{kind}/{id} -> status pending|processing|completed|failed, content_url (signed, ~2h)
Video model ids seen: veo-3.1-generate-001, veo-3.1-fast-generate-001, creatify-aurora,
bytedance-seedance-v2(.5|-fast|-mini) (ByteDance needs explicit approval from ElevenLabs support).
"""
from __future__ import annotations

import base64
import sys
import time
from pathlib import Path

import requests

from . import config

API = "https://api.elevenlabs.io/v1/flows"


def _headers() -> dict:
    return {"xi-api-key": config.require_env("ELEVENLABS_API_KEY"), "Content-Type": "application/json"}


def _image_ref(path: Path) -> dict:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "inline_base64", "mime_type": mime, "content_base64": base64.b64encode(path.read_bytes()).decode()}


def _run(kind: str, body: dict, out: Path, timeout: float) -> Path:
    r = requests.post(f"{API}/{kind}", headers=_headers(), json=body, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"{kind} {body['model_id']}: {r.status_code} {r.text[:300]}")
    jid = r.json()["id"]
    t0 = time.time()
    while True:
        time.sleep(6)
        d = requests.get(f"{API}/{kind}/{jid}", headers=_headers(), timeout=60).json()
        st = d.get("status")
        if st == "completed" and d.get("content_url"):
            break
        if st not in ("pending", "processing", "queued", "running", "generating"):
            raise RuntimeError(f"{kind} {body['model_id']}: job {jid} {st}: {str(d)[:300]}")
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{kind} {body['model_id']}: job {jid} timed out after {int(timeout)}s")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(requests.get(d["content_url"], timeout=300).content)
    return out


def generate_image(prompt: str, out: Path, ref: Path | None = None) -> Path:
    models = [m for m in config.env("XI_IMAGE_MODEL", "gemini-3.1-flash-image,gemini-3-pro-image,gemini-2.5-flash-image").split(",") if m]
    last = None
    for model in models:
        body = {"model_id": model, "prompt": prompt, "aspect_ratio": "9:16"}
        if ref:
            body["images"] = [_image_ref(ref)]
        try:
            return _run("image", body, out, timeout=240)
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[xi]   image {model} failed: {str(e)[:200]}", file=sys.stderr)
    raise RuntimeError(f"ElevenLabs image generation failed: {last}")


def generate_video(prompt: str, out: Path, ref: Path | None = None) -> Path:
    """One 9:16 clip (veo = 8s/720p). Models tried in order of XI_VIDEO_MODEL."""
    models = [m for m in config.env("XI_VIDEO_MODEL", "veo-3.1-fast-generate-001,veo-3.1-generate-001").split(",") if m]
    last = None
    for model in models:
        body = {"model_id": model, "prompt": prompt, "aspect_ratio": "9:16"}
        if model.startswith("veo"):
            body["resolution"] = config.env("XI_VIDEO_RES", "720p")
            body["generate_audio"] = False
        elif model.startswith("bytedance"):
            body["resolution"] = "720p"
            body["generate_audio"] = False
        if ref:
            body["images"] = [_image_ref(ref)]
        try:
            return _run("video", body, out, timeout=float(config.env("XI_VIDEO_TIMEOUT", "900")))
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[xi]   video {model} failed: {str(e)[:200]}", file=sys.stderr)
    raise RuntimeError(f"ElevenLabs video generation failed: {last}")


def _audio_ref(path: Path) -> dict:
    mime = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4"}.get(path.suffix.lower().lstrip("."), "audio/wav")
    return {"type": "inline_base64", "mime_type": mime, "content_base64": base64.b64encode(path.read_bytes()).decode()}


def generate_talking(face: Path, audio: Path, out: Path) -> Path:
    """Lip-synced talking presenter from one still of the owner + the narration wav (creatify-aurora)."""
    body = {"model_id": config.env("XI_TALK_MODEL", "creatify-aurora"), "image": _image_ref(face), "audio": _audio_ref(audio),
            "resolution": config.env("XI_TALK_RES", "720p")}
    return _run("video", body, out, timeout=float(config.env("XI_VIDEO_TIMEOUT", "900")))
