"""Deterministic tools for the Claude Code studio. Claude does the thinking (topics, scripts, edit decisions,
review); these commands are its hands. Every command prints what it wrote and exits non-zero on failure.

  python -m pipeline channels                    -> .state/channels.json (recent Shorts titles per channel)
  python -m pipeline inspect <youtube url>       -> .state/refs/<id>/ (meta.json, transcript.json, frames.jpg)
  python -m pipeline teleprompter <script.json>  -> <folder>/teleprompter.html
  python -m pipeline transcribe <recording.mp4>  -> <folder>/words.json (faster-whisper word timings + silences)
  python -m pipeline compose <plan.json>         -> ready/<name>.mp4 + <name>.jpg + <name>.md
  python -m pipeline review <video.mp4>          -> <folder>/review/ (contact sheet, loudness, duration, stream info)
"""
from __future__ import annotations

import json
import re
import shutil
import os
import struct
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from . import config

W, H, FPS = 1080, 1920, 30
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
LAYOUTS = ("corner", "circle-top", "split", "full")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        sys.exit(f"[tools] command failed: {' '.join(str(c) for c in cmd[:6])} ...\n{r.stderr[-1500:]}")
    return r


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _ytdlp() -> list[str]:
    return ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]


# ----------------------------------------------------------------------------- channels
def channels(limit: int = 15) -> Path:
    """Recent Shorts (title, views, url) for every channel in channels.txt -> .state/channels.json."""
    f = config.ROOT / "channels.txt"
    chans = [l.split("#")[0].strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if not chans:
        sys.exit("[channels] channels.txt is empty - add one YouTube channel URL per line")
    result = []
    for ch in chans:
        url = ch.rstrip("/")
        url = url if url.endswith("/shorts") else url + "/shorts"
        r = subprocess.run(_ytdlp() + ["--flat-playlist", "--no-warnings", "--playlist-end", str(limit), "--print",
                                        "%(id)s\t%(title)s\t%(view_count)s", url], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        items = []
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                views = parts[2] if len(parts) > 2 and parts[2] not in ("NA", "None") else None
                items.append({"id": parts[0], "title": parts[1], "views": int(views) if views and views.isdigit() else None,
                              "url": f"https://www.youtube.com/shorts/{parts[0]}"})
        if not items:
            print(f"[channels] {ch}: nothing fetched ({r.stderr.strip()[:120]})", file=sys.stderr)
        result.append({"channel": ch, "shorts": items})
        print(f"[channels] {ch}: {len(items)} shorts")
    config.STATE_DIR.mkdir(exist_ok=True)
    out = config.STATE_DIR / "channels.json"
    out.write_text(json.dumps({"date": date.today().isoformat(), "channels": result}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(out)
    return out


# ----------------------------------------------------------------------------- inspect (reference Short)
def inspect(url: str) -> Path:
    """Download a Short and extract what Claude needs to understand it without Gemini:
    meta.json (title, description, duration, channel), transcript.json (Whisper, original language, with timings),
    frames.jpg (contact sheet, 4x6 = 24 frames in order), reference.mp4."""
    vid = config.youtube_id(url)
    out = config.STATE_DIR / "refs" / vid
    out.mkdir(parents=True, exist_ok=True)
    video = out / "reference.mp4"
    if not video.exists():
        _run(_ytdlp() + ["-q", "--no-warnings", "-f", "bv*[height<=1920]+ba/b", "--merge-output-format", "mp4",
                         "--write-info-json", "-o", str(video), url])
    info = next(out.glob("*.info.json"), None)
    meta = {"url": url, "id": vid}
    if info:
        j = json.loads(info.read_text(encoding="utf-8"))
        meta.update({k: j.get(k) for k in ("title", "description", "duration", "channel", "uploader", "view_count",
                                              "like_count", "upload_date", "tags")})
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    dur = duration(video)
    n = 24
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
          f"fps={n / max(dur, 1):.4f},scale=270:480,tile=4x6", "-frames:v", "1", str(out / "frames.jpg")])
    transcribe(video, out / "transcript.json", language=None)
    print(f"[inspect] {out}  ({dur:.0f}s) -> meta.json, transcript.json, frames.jpg")
    print(out)
    return out


# ----------------------------------------------------------------------------- transcribe (faster-whisper)
def transcribe(media: Path, out: Path | None = None, language: str | None = "te") -> Path:
    """Word-level timings of a recording -> words.json. Needs `pip install faster-whisper` (CPU is fine)."""
    media = Path(media)
    out = out or media.with_name("words.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".16k.wav")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)])
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("[transcribe] faster-whisper missing: .venv\\Scripts\\pip install faster-whisper")
    model_name = config.env("WHISPER_MODEL", "small")
    print(f"[transcribe] whisper {model_name} on {media.name} ...", flush=True)
    t0 = time.time()
    print("[transcribe] loading model ...", flush=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as wf:  # decode ourselves: avoids PyAV version mismatches on Windows
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    print(f"[transcribe] model loaded in {time.time() - t0:.0f}s; decoding {duration(wav):.1f}s audio ...", flush=True)
    segs, info = model.transcribe(pcm, language=language, word_timestamps=True, vad_filter=True,
                                  vad_parameters={"min_silence_duration_ms": 400})
    words, segments = [], []
    for n, s in enumerate(segs, 1):
        segments.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        for w in s.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)})
        print(f"[transcribe] segment {n}: {s.end:.1f}s decoded", flush=True)
    total = duration(wav)
    silences, last = [], 0.0
    for w in words:
        if w["s"] - last >= 0.6:
            silences.append({"s": round(last, 2), "e": round(w["s"], 2)})
        last = w["e"]
    if total - last >= 0.6:
        silences.append({"s": round(last, 2), "e": round(total, 2)})
    data = {"media": str(media), "duration": round(total, 2), "language": info.language,
            "language_probability": round(float(info.language_probability), 2), "segments": segments, "words": words,
            "silences": silences}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    wav.unlink(missing_ok=True)
    print(f"[transcribe] {len(words)} words, {len(silences)} silences >=0.6s, {total:.1f}s, took {time.time() - t0:.0f}s")
    print(out)
    return out


# ----------------------------------------------------------------------------- teleprompter
TELEPROMPTER_HTML = """<!doctype html><html lang="te"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>
 :root{{--accent:#ffd54a;--panel:rgba(18,18,18,.92)}}
 *{{box-sizing:border-box}}
 html{{background:#000}}
 body{{margin:0;background:radial-gradient(circle at 50% 35%,#151515 0,#050505 48%,#000 100%);color:#fff;font-family:"Nirmala UI","Noto Sans Telugu",sans-serif;overflow:hidden}}
 #bar{{position:fixed;top:0;left:0;right:0;min-height:54px;padding:10px 18px;background:linear-gradient(#111 60%,rgba(17,17,17,.72));font:14px system-ui;color:#aaa;z-index:9;display:flex;align-items:center;gap:12px}}
 #bar b{{color:#fff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}} #st{{white-space:nowrap;color:#ddd}}
 #line{{position:fixed;top:43%;left:3vw;right:3vw;border-top:2px solid rgba(255,80,80,.7);z-index:3;pointer-events:none}}
 #line:before,#line:after{{content:"";position:absolute;top:-7px;width:12px;height:12px;border-radius:50%;background:#ff5050}}
 #line:before{{left:-2px}} #line:after{{right:-2px}}
 #txt{{width:min(92vw,1000px);margin:0 auto;padding:43vh 2vw 70vh;font-size:clamp(34px,5.2vw,{size}px);line-height:1.48;font-weight:650;text-align:center;letter-spacing:.01em;text-wrap:balance}}
 .beat{{margin:0 0 1.35em;text-shadow:0 2px 12px #000}} .hook{{color:var(--accent)}} .cta{{color:#78d7ff}} .cue{{font:600 .32em/1.4 system-ui;color:#888;letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:.65em}}
 #controls{{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);display:flex;gap:8px;align-items:center;padding:8px;border:1px solid #333;border-radius:14px;background:var(--panel);z-index:10;box-shadow:0 8px 30px #000}}
 button{{border:1px solid #444;border-radius:9px;background:#242424;color:#eee;padding:9px 13px;font:600 14px system-ui;cursor:pointer}}
 button:hover{{background:#333}} #play{{background:#f2c94c;color:#111;border-color:#f2c94c;min-width:92px}}
 .mirror #txt{{transform:scaleX(-1)}} .mirror #line{{transform:scaleX(-1)}}
 @media(max-width:650px){{#bar{{padding:9px 12px}}#bar b{{display:none}}#controls{{bottom:8px;width:calc(100% - 16px);justify-content:center}}button{{padding:9px 10px}}#txt{{width:96vw;padding-left:3vw;padding-right:3vw}}}}
</style></head><body>
<div id="bar"><b>{title}</b><span>Space play · L listen · ↑/↓ speed · R restart · M mirror · +/- size</span><span id="st">Paused · <span id="sp">{speed}</span> px/s</span></div>
<div id="line"></div>
<main id="txt" dir="auto">{body}</main>
<nav id="controls"><button id="restart">Restart</button><button id="listen">Listen</button><button id="slower">Slower</button><button id="play">Start</button><button id="faster">Faster</button><button id="mirror">Mirror</button><button id="full">Full screen</button></nav>
<script>
 let speed={speed},run=false,y=0,last=null,txt=document.getElementById('txt'),fs={size};
 const play=document.getElementById('play'),listen=document.getElementById('listen'),sp=document.getElementById('sp'),st=document.getElementById('st');
 const audioAvailable={audio},audio=new Audio('teleprompter.mp3');
 function status(){{play.textContent=run?'Pause':'Start';sp.textContent=speed;st.firstChild.textContent=(run?'Running':'Paused')+' · ';}}
 function toggle(){{run=!run;status()}}
 function restart(){{y=0;window.scrollTo(0,0);run=false;audio.pause();audio.currentTime=0;speechSynthesis.cancel();listen.textContent='Listen';status()}}
 function scriptText(){{return [...document.querySelectorAll('.beat')].map(p=>{{const q=p.cloneNode(true);q.querySelectorAll('.cue').forEach(x=>x.remove());return q.textContent.trim()}}).join('. ')}}
 function speak(){{
  if(audioAvailable){{
   if(!audio.paused){{audio.pause();listen.textContent='Listen';status();return}}
   speechSynthesis.cancel();audio.play();listen.textContent='Stop audio';st.firstChild.textContent='Listening · ';return
  }}
  if(speechSynthesis.speaking){{speechSynthesis.cancel();listen.textContent='Listen';return}}
  const u=new SpeechSynthesisUtterance(scriptText()),voices=speechSynthesis.getVoices();
  u.lang='te-IN';u.rate=.9;u.pitch=1;
  u.voice=voices.find(v=>v.lang.toLowerCase().startsWith('te'))||null;
  u.onstart=()=>{{listen.textContent='Stop audio';st.firstChild.textContent=(u.voice?'Listening':'Listening (default voice)')+' · '}};
  u.onend=u.onerror=()=>{{listen.textContent='Listen';status()}};
  speechSynthesis.speak(u);
 }}
 function step(t){{ if(run){{ if(last!==null){{ y+= speed*(t-last)/1000; window.scrollTo(0,y);}} last=t; }} else last=null; requestAnimationFrame(step);}}
 requestAnimationFrame(step);
 document.addEventListener('keydown',e=>{{
  if(e.code==='Space'){{toggle();e.preventDefault();}}
  if(e.key==='l'||e.key==='L'){{speak();}}
  if(e.code==='ArrowUp'){{speed+=10;}} if(e.code==='ArrowDown'){{speed=Math.max(10,speed-10);}}
  if(e.key==='r'||e.key==='R'){{restart();}}
  if(e.key==='m'||e.key==='M'){{document.body.classList.toggle('mirror');}}
  if(e.key==='+'||e.key==='='){{fs+=4;txt.style.fontSize=fs+'px';}} if(e.key==='-'){{fs=Math.max(24,fs-4);txt.style.fontSize=fs+'px';}}
  status();
 }});
 play.onclick=toggle; listen.onclick=speak; document.getElementById('restart').onclick=restart;
 document.getElementById('slower').onclick=()=>{{speed=Math.max(10,speed-10);status()}};
 document.getElementById('faster').onclick=()=>{{speed+=10;status()}};
 document.getElementById('mirror').onclick=()=>document.body.classList.toggle('mirror');
 document.getElementById('full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
 audio.onended=()=>{{listen.textContent='Listen';status()}};
 status();
</script></body></html>"""


def teleprompter(script_path: Path) -> Path:
    """script.json (see CLAUDE.md schema) -> teleprompter.html next to it."""
    script_path = Path(script_path)
    s = json.loads(script_path.read_text(encoding="utf-8"))
    parts = [f'<p class="beat hook"><span class="cue">HOOK - look straight, energy up</span>{s["hook_te"]}</p>']
    for b in s["beats"]:
        cue = b.get("delivery") or ""
        parts.append(f'<p class="beat"><span class="cue">{b["id"]}. {cue}</span>{b["text_te"]}</p>')
    parts.append(f'<p class="beat cta"><span class="cue">CTA - smile</span>{s["cta_te"]}</p>')
    speech = ". ".join([s["hook_te"], *(b["text_te"] for b in s["beats"]), s["cta_te"]])
    audio = script_path.with_name("teleprompter.mp3")
    try:
        import asyncio
        import edge_tts
        voice = config.env("PROMPTER_VOICE", "te-IN-MohanNeural")
        asyncio.run(edge_tts.Communicate(speech, voice, rate="-5%").save(str(audio)))
        print(f"[teleprompter] audio: {audio} ({voice})")
    except Exception as e:  # browser speech synthesis remains as an offline fallback
        audio.unlink(missing_ok=True)
        print(f"[teleprompter] Telugu audio unavailable ({e}); browser voice fallback only", file=sys.stderr)
    html = TELEPROMPTER_HTML.format(title=s.get("title_te", "Teleprompter"), body="\n".join(parts),
                                    speed=int(config.env("PROMPTER_SPEED", "55")), size=int(config.env("PROMPTER_FONT", "54")),
                                    audio="true" if audio.exists() else "false")
    out = script_path.with_name("teleprompter.html")
    out.write_text(html, encoding="utf-8")
    print(f"[teleprompter] {out}  (open in a browser; SPACE to start)")
    print(out)
    return out


# ----------------------------------------------------------------------------- compose (plan.json -> final)
def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02}:{s:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


class _Remap:
    """Recording time -> output time after cutting (keep segments concatenated)."""

    def __init__(self, keep: list[list[float]]):
        self.keep = keep
        self.offsets, acc = [], 0.0
        for s, e in keep:
            self.offsets.append(acc)
            acc += e - s
        self.total = acc

    def __call__(self, t: float, end: bool = False) -> float:
        # keep may be re-ordered (e.g. a later line used as the hook): first find the segment that contains t.
        # A shared boundary belongs to the segment it ENDS when `end` (beat/caption ends), else to the one it starts.
        for (s, e), off in zip(self.keep, self.offsets):
            if (s < t <= e) if end else (s <= t < e):
                return off + (t - s)
        for (s, e), off in zip(self.keep, self.offsets):
            if t < s:
                return off
            if t <= e:
                return off + (t - s)
        return self.total


def _cut(src: Path, keep: list[list[float]], out: Path) -> Path:
    parts = []
    for i, (s, e) in enumerate(keep):
        parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
    streams = "".join(f"[v{i}][a{i}]" for i in range(len(keep)))
    fc = ";".join(parts) + f";{streams}concat=n={len(keep)}:v=1:a=1[v][a]"
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
          "-vf" if False else "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "pcm_s16le", str(out)])
    return out


_POLL_NEXT_OK = 0.0  # free Pollinations tier: 1 image per 45 s per IP (HTTP 402 FREE_LIMIT otherwise)


def _pollinations_image(full: str, img: Path, attempts: int = 5) -> bool:
    """Fetch one 9:16 image from the free Pollinations endpoint, pacing requests and honouring its retry hint."""
    global _POLL_NEXT_OK
    import urllib.parse
    import requests
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(full[:800])
    params = {"width": 1080, "height": 1920, "nologo": "true"}
    for attempt in range(1, attempts + 1):
        wait = _POLL_NEXT_OK - time.time()
        if wait > 0:
            print(f"[compose]   pollinations: pacing {wait:.0f}s (free tier = 1 image / 45 s)", flush=True)
            time.sleep(wait)
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException as e:  # noqa: BLE001
            print(f"[compose]   pollinations error ({str(e)[:100]}); retry {attempt}/{attempts}", file=sys.stderr)
            _POLL_NEXT_OK = time.time() + 15
            continue
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") and len(r.content) > 10_000:
            img.write_bytes(r.content)
            _POLL_NEXT_OK = time.time() + 46
            return True
        retry = 46.0
        m = re.search(r"[Rr]etry after (\d+)", r.text[:600])
        hdr = r.headers.get("Retry-After", "")
        if m:
            retry = float(m.group(1)) + 2
        elif hdr.isdigit():
            retry = float(hdr) + 2
        print(f"[compose]   pollinations HTTP {r.status_code}; retry {attempt}/{attempts} in {retry:.0f}s", file=sys.stderr)
        _POLL_NEXT_OK = time.time() + min(retry, 120)
    return False


def _broll(beat: dict, seconds: float, out: Path, style: str) -> Path | None:
    """Background per beat: ElevenLabs Veo clip (credits) or image+zoom; cached by beat id. None -> presenter only."""
    if out.exists():
        return out
    prompt = (beat.get("broll_prompt") or "").strip()
    if not prompt:
        return None
    full = (f"{prompt}. {style} Vertical 9:16, photorealistic, sharp, cinematic lighting, smooth slow camera move, "
            "no on-screen text, no captions, no watermark, no logos, no person talking to camera.")
    provider = config.env("BROLL_PROVIDER", "elevenlabs" if config.env("ELEVENLABS_API_KEY") else "none").lower()
    raw = out.with_name(out.stem + "_raw.mp4")
    img = out.with_suffix(".png")
    if provider == "elevenlabs":
        from . import xi_media
        try:
            if not raw.exists():
                xi_media.generate_video(full, raw)
        except Exception as e:  # noqa: BLE001
            print(f"[compose]   veo failed ({str(e)[:120]}) - trying still image", file=sys.stderr)
            try:
                if not img.exists():
                    xi_media.generate_image(full, img)
            except Exception as e2:  # noqa: BLE001
                print(f"[compose]   image failed ({str(e2)[:120]}) - presenter only", file=sys.stderr)
                return None
    elif provider == "pollinations":
        if not img.exists() and not _pollinations_image(full, img):
            return None
    else:
        return None
    if raw.exists():
        _run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(raw), "-t", f"{seconds:.3f}", "-an",
              "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    else:
        frames = max(int(seconds * FPS), FPS)
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(img), "-vf",
              f"crop=iw:ih*0.94:0:0,scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
              f"zoompan=z='min(zoom+{0.25 / frames:.6f},1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},format=yuv420p",
              "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    return out


def _presenter_segment(cut: Path, start: float, end: float, out: Path, zoom: float = 1.0, grade: str = "") -> Path:
    """Presenter full-frame. zoom > 1 = editor's punch-in (crop anchored near the top so the head is not clipped).
    grade = optional ffmpeg filter (e.g. "eq=gamma=1.12") from plan.json to lift an under-exposed face."""
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if zoom > 1.0:
        vf += f",scale={round(W * zoom / 2) * 2}:{round(H * zoom / 2) * 2},crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.08"
    if grade:
        vf += f",{grade}"
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(cut), "-an",
          "-vf", f"{vf},fps={FPS},format=yuv420p",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(out)])
    return out


def _layout(bg: Path, pres: Path, layout: str, out: Path, accent: str, seconds: float) -> Path:
    """Composite presenter over/beside the background according to the layout template."""
    acc = accent.lstrip("#")
    if layout == "corner":
        fc = (f"[1:v]scale=460:-2[p];[0:v][p]overlay=x=40:y=H-h-300:shortest=1,format=yuv420p")
    elif layout == "circle-top":
        # Presenter in a circle at the TOP-RIGHT (owner's call), leaving the background subject visible and the
        # caption/title zones free. Intentional, not pasted: feathered edge, soft shadow/halo, thin accent ring,
        # background stays bright - it is the highlight, the face is secondary.
        d = 470
        c = d / 2
        pad = 80
        cs = d + pad
        cc = cs / 2
        x_right = 48   # margin from the right edge
        y = 150
        fc = (f"[0:v]eq=saturation=1.06[bgd];"  # background is the hero: keep it bright and sharp, no dimming/vignette
              f"[1:v]crop='min(iw,ih*0.62)':'min(iw,ih*0.62)':(iw-ow)/2:ih*0.06,scale={d}:{d},format=rgba,"
              f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='clip(({c}-hypot(X-{c},Y-{c}))*64,0,255)'[p];"
              f"color=c=black:s={cs}x{cs},format=rgba,"
              f"geq=r='0':g='0':b='0':a='clip(({c + 24}-hypot(X-{cc},Y-{cc}))*7,0,150)'[shadow];"
              f"color=c=0x{acc}:s={cs}x{cs},format=rgba,"
              f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='clip(min(hypot(X-{cc},Y-{cc})-{c + 2},{c + 12}-hypot(X-{cc},Y-{cc}))*64,0,255)'[ring];"
              f"[bgd][shadow]overlay=x=W-w-{x_right - pad // 2}:y={y - pad // 2 + 18}:shortest=1[b1];"
              f"[b1][ring]overlay=x=W-w-{x_right - pad // 2}:y={y - pad // 2}:shortest=1[b2];"
              f"[b2][p]overlay=x=W-w-{x_right}:y={y}:shortest=1,format=yuv420p")
    elif layout == "split":
        fc = (f"[0:v]crop={W}:{H // 2}:0:(ih-{H // 2})/2[top];[1:v]crop={W}:{H // 2}:0:(ih-{H // 2})/2*0.7[bot];"
              f"[top][bot]vstack=inputs=2,format=yuv420p")
    else:
        return pres
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(bg), "-i", str(pres), "-filter_complex", fc, "-r", str(FPS),
          "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(out)])
    return out


def compose(plan_path: Path) -> Path:
    """plan.json (written by Claude, schema in CLAUDE.md) -> ready/<name>.mp4 (+ .jpg thumbnail, .md metadata)."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    rec = Path(plan["recording"])
    if not rec.is_absolute():
        rec = config.ROOT / rec
    if not rec.exists():
        sys.exit(f"[compose] recording not found: {rec}")
    name = plan.get("name") or re.sub(r"[^\w-]+", "-", rec.stem)[:60]
    ready = config.ROOT / plan.get("out_dir", "ready")
    ready.mkdir(parents=True, exist_ok=True)
    work = plan_path.parent / "build"
    work.mkdir(parents=True, exist_ok=True)
    layout = plan.get("layout", "corner")
    if layout not in LAYOUTS:
        sys.exit(f"[compose] layout must be one of {LAYOUTS}")
    accent = plan.get("accent", "#ffd54a")
    style = plan.get("broll_style", "")
    keep = [[float(a), float(b)] for a, b in plan["keep"]]
    remap = _Remap(keep)

    print(f"[compose] cut: {len(keep)} segments -> {remap.total:.1f}s")
    cut = _cut(rec, keep, work / "cut.mkv")

    beats = plan["beats"]
    clips, full_frame = [], set()  # full_frame: beat ids shown presenter-only (labels move off the face)
    provider = config.env("BROLL_PROVIDER", "elevenlabs" if config.env("ELEVENLABS_API_KEY") else "none").lower()
    missing_bg: list[int] = []  # explain beats that asked for a background the provider could not deliver
    for b in beats:
        s, e = remap(float(b["start"])), remap(float(b["end"]), end=True)
        if e - s < 0.3:
            continue
        kind = b.get("kind", "explain")
        pres = _presenter_segment(cut, s, e, work / f"pres_{b['id']}.mp4", float(b.get("zoom", 1.0)), plan.get("grade", ""))
        print(f"[compose] beat {b['id']} ({kind}, {e - s:.1f}s)")
        if kind in ("hook", "cta") or layout == "full":
            clips.append(pres); full_frame.add(b["id"])
            continue
        bg = _broll(b, e - s + 0.5, work / f"bg_{b['id']}.mp4", style)
        if bg is None:
            if (b.get("broll_prompt") or "").strip() and provider != "none":
                missing_bg.append(b["id"])
                print(f"[compose]   beat {b['id']}: background FAILED ({provider}) - presenter full-frame", file=sys.stderr)
            else:
                print(f"[compose]   beat {b['id']}: no background requested - presenter full-frame")
            clips.append(pres); full_frame.add(b["id"])
            continue
        clips.append(_layout(bg, pres, b.get("layout") or layout, work / f"beat_{b['id']}.mp4", accent, e - s))

    if missing_bg and not plan.get("allow_presenter_fallback"):
        sys.exit(f"[compose] FAILED: no background for explain beat(s) {missing_bg} (BROLL_PROVIDER={provider}). "
                 "A Short with the presenter full-frame on explain beats is not the agreed look. Fix the cause "
                 "(provider limit/network/prompt) and re-run compose - finished backgrounds are cached in build/, "
                 "only the missing ones are fetched. Set plan.allow_presenter_fallback=true only for a deliberate choice.")

    ai_beats = sum(1 for b in beats if b["id"] not in full_frame and (work / f"beat_{b['id']}.mp4") in clips)
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips), encoding="utf-8")
    joined = work / "joined.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-r", str(FPS),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(joined)])

    # captions + title card + beat labels as one ASS file
    font = config.env("SUBTITLE_FONT", "Nirmala UI")
    ass = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Shorts safe zone: keep text out of the top ~220 px (search/menu) and bottom ~420 px (title/channel/buttons)
        f"Style: Cap,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,440,1",
        f"Style: CapHi,{font},86,&H00{accent[5:7]}{accent[3:5]}{accent[1:3]},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,440,1",
        f"Style: Title,{font},78,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,14,0,8,70,70,230,1",
        f"Style: Label,{font},52,&H00000000,&H00FFFFFF,&H00{accent[5:7]}{accent[3:5]}{accent[1:3]},&H00{accent[5:7]}{accent[3:5]}{accent[1:3]},-1,0,0,0,100,100,0,0,3,16,0,8,90,90,1040,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    title = plan.get("title_te")
    if title and beats:
        h0, h1 = remap(float(beats[0]["start"])), remap(float(beats[0]["end"]), end=True)
        ass.append(f"Dialogue: 2,{_ass_time(h0)},{_ass_time(min(h1, h0 + 4.0))},Title,,0,0,0,,{_esc(title)}")
    for b in beats:
        lab = (b.get("label_te") or "").strip()
        if lab and b.get("kind", "explain") not in ("hook", "cta"):
            mv = 230 if b["id"] in full_frame else 0  # presenter full-frame: label in the top band, not on the face
            ass.append(f"Dialogue: 1,{_ass_time(remap(float(b['start'])))},{_ass_time(remap(float(b['end']), end=True))},Label,,0,0,{mv},,{_esc(lab)}")
        for c in b.get("captions", []):
            cs, ce = remap(float(c["start"])), remap(float(c["end"]), end=True)
            if ce - cs < 0.15:
                continue
            ass.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce - 0.03)},Cap,,0,0,0,,{_esc(c['text'])}")
    ass_path = work / "captions.ass"
    ass_path.write_text("\n".join(ass), encoding="utf-8")

    final = ready / f"{name}.mp4"
    tmp_final = work / f"{name}.final.tmp.mp4"
    ass_arg = ass_path.resolve().as_posix().replace(":", "\\:")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-i", str(cut)]
    af = config.env("VOICE_CHAIN", "highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=8:release=120:makeup=4,"
                                   "alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11")
    music = plan.get("music")
    fc = f"[0:v]subtitles='{ass_arg}'[v];[1:a]{af}[voice]"
    mix, idx = ["[voice]"], 2
    if music:
        mpath = Path(music) if Path(music).is_absolute() else config.ROOT / music
        cmd += ["-stream_loop", "-1", "-i", str(mpath)]
        fc += f";[{idx}:a]volume={float(plan.get('music_volume', 0.08))},afade=t=out:st={max(0.0, remap.total - 1.5):.2f}:d=1.5[m]"
        mix.append("[m]"); idx += 1
    # sound effects: [{"at": recording_sec | "out": output_sec, "file": "assets/sfx/whoosh.mp3", "gain": 0.5}]
    for n, fx in enumerate(plan.get("sfx", [])):
        fpath = Path(fx["file"]) if Path(fx["file"]).is_absolute() else config.ROOT / fx["file"]
        if not fpath.exists():
            print(f"[compose]   sfx missing, skipped: {fpath}", file=sys.stderr)
            continue
        at = float(fx["out"]) if "out" in fx else remap(float(fx["at"]))
        cmd += ["-i", str(fpath)]
        fc += f";[{idx}:a]volume={float(fx.get('gain', 0.5))},adelay={int(at * 1000)}|{int(at * 1000)}[fx{n}]"
        mix.append(f"[fx{n}]"); idx += 1
    if len(mix) > 1:
        fc += f";{''.join(mix)}amix=inputs={len(mix)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.84:level=0[a]"  # music/SFX can push true peak past -1 dBTP
    else:
        fc += ";[voice]anull[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{remap.total:.3f}", "-c:v", "libx264",
            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(tmp_final)]
    _run(cmd)
    publish(tmp_final, final)

    thumb_at = float(plan.get("thumbnail_sec", remap(float(beats[0]["start"])) + 0.8 if beats else 1.0))
    thumbnail(joined, thumb_at, plan.get("thumbnail_text_te") or plan.get("title_te") or "", accent, ready / f"{name}.jpg", font)
    meta = [f"# {plan.get('title_te', name)}", "", plan.get("description_te", ""), "",
            " ".join(plan.get("hashtags", [])), "", f"Duration: {duration(final):.1f}s  Layout: {layout}"
            + (" (rendered presenter full-frame: no backgrounds generated)" if not ai_beats and layout != "full" else ""),
            (f"Label at upload: 'Altered or synthetic content' = YES - AI-generated backgrounds on {ai_beats} beat(s)."
             if ai_beats else "Label at upload: 'Altered or synthetic content' = NO - no AI-generated visuals in this render.")]
    (ready / f"{name}.md").write_text("\n".join(meta), encoding="utf-8")
    print(f"[compose] ready: {final}  ({duration(final):.1f}s)")
    print(final)
    return final


# ----------------------------------------------------------------------------- verify / publish
def _atoms(path: Path) -> list[tuple[str, int, int]]:
    out, pos, end = [], 0, path.stat().st_size
    with open(path, "rb") as f:
        while pos + 8 <= end:
            f.seek(pos)
            sz, typ = struct.unpack(">I4s", f.read(8))
            if sz == 1:
                sz = struct.unpack(">Q", f.read(8))[0]
            if sz == 0:
                sz = end - pos
            out.append((typ.decode("latin1"), pos, sz))
            pos += sz
    return out


def verify(video: Path) -> dict:
    """Prove a delivered MP4 is complete and plays everywhere (Windows Media Player, YouTube, phones):
    every atom accounted for, moov before mdat (faststart), H.264 yuv420p <= level 4.2 + AAC 48k stereo,
    9:16 1080x1920, duration > 0, and a FULL decode of every video frame and audio packet with zero errors.
    Returns the report; report["ok"] is the single gate."""
    video = Path(video)
    rep: dict = {"video": str(video), "ok": False, "errors": []}
    err = rep["errors"]
    if not video.exists() or video.stat().st_size == 0:
        err.append("file missing or empty"); return rep
    try:
        atoms = _atoms(video)
    except Exception as e:  # noqa: BLE001
        atoms = []; err.append(f"atom parse failed: {e}")
    names = [a[0] for a in atoms]
    rep["atoms"] = names
    if atoms and atoms[-1][1] + atoms[-1][2] != video.stat().st_size:
        err.append("atom sizes do not add up to file size (truncated / still being written)")
    if "moov" not in names or "mdat" not in names:
        err.append("missing moov or mdat (unfinished mp4)")
    elif names.index("moov") > names.index("mdat"):
        err.append("moov after mdat (no faststart)")
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_type,codec_name,profile,level,pix_fmt,width,height,sample_rate,channels,r_frame_rate"
                         ":format=duration,nb_streams", "-of", "json", str(video)], capture_output=True, text=True)
    info = json.loads(pr.stdout or "{}")
    st = {x.get("codec_type"): x for x in info.get("streams", [])}
    rep["streams"] = info.get("streams"); rep["duration_sec"] = float(info.get("format", {}).get("duration", 0) or 0)
    v, a = st.get("video"), st.get("audio")
    if not v: err.append("no video stream")
    else:
        if v.get("codec_name") != "h264": err.append(f"video codec {v.get('codec_name')} != h264")
        if v.get("pix_fmt") != "yuv420p": err.append(f"pix_fmt {v.get('pix_fmt')} != yuv420p")
        if int(v.get("level") or 0) > 42: err.append(f"h264 level {v.get('level')} > 4.2")
        if (v.get("width"), v.get("height")) != (W, H): err.append(f"size {v.get('width')}x{v.get('height')} != {W}x{H}")
    if not a: err.append("no audio stream")
    else:
        if a.get("codec_name") != "aac": err.append(f"audio codec {a.get('codec_name')} != aac")
        if str(a.get("sample_rate")) != "48000": err.append(f"sample_rate {a.get('sample_rate')} != 48000")
    if rep["duration_sec"] <= 0: err.append("duration is zero / unknown")
    if rep["duration_sec"] > 180: err.append("longer than 180s (not a Short)")
    dec = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if dec.returncode != 0 or dec.stderr.strip():
        err.append("full decode failed: " + (dec.stderr.strip().splitlines() or ["non-zero exit"])[-1])
    rep["full_decode"] = dec.returncode == 0 and not dec.stderr.strip()
    rep["ok"] = not err
    return rep


def publish(tmp: Path, final: Path) -> Path:
    """Gate + atomic move: the file appears in ready/ only after verify() passes, so nobody (owner, watcher,
    uploader) can ever open a half-written or broken MP4. On failure the tmp file is kept for diagnosis."""
    rep = verify(tmp)
    (final.parent / f"{final.stem}.verify.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if not rep["ok"]:
        raise RuntimeError(f"[publish] output failed verification, NOT published: {rep['errors']} (kept {tmp})")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(tmp, final)
    print(f"[publish] verified ({rep['duration_sec']:.1f}s, full decode ok) -> {final}")
    return final


def thumbnail(video: Path, at: float, text: str, accent: str, out: Path, font: str = "Nirmala UI") -> Path:
    """Frame + big Telugu title (2 lines max, accent underline) -> out (1080x1920) and out_wide (1280x720)."""
    frame = out.with_suffix(".frame.png")
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", str(frame)])
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text).strip()  # fonts lack emoji
    words = text.split()
    lines = [" ".join(words[:len(words) // 2 or 1]), " ".join(words[len(words) // 2 or 1:])] if len(words) > 3 else [text]
    txt = "\\N".join(_esc(l) for l in lines if l)
    acc = accent.lstrip("#")
    ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           f"Style: T,{font},118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,9,4,8,50,50,110,1",
           f"Style: U,{font},118,&H00{acc[4:6]}{acc[2:4]}{acc[0:2]},&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,8,50,50,110,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
           f"Dialogue: 0,0:00:00.00,0:00:01.00,T,,0,0,0,,{txt}"]
    ass_p = out.with_suffix(".thumb.ass"); ass_p.write_text("\n".join(ass), encoding="utf-8")
    ass_arg = ass_p.resolve().as_posix().replace(":", "\\:")
    # title band kept in the top 420 px (above the head in a normal selfie framing); accent rule centred under it
    vf = (f"eq=contrast=1.08:saturation=1.15,drawbox=x=0:y=0:w={W}:h=420:color=black@0.45:t=fill,"
          f"drawbox=x={(W - 360) // 2}:y=400:w=360:h=14:color=0x{acc}:t=fill,subtitles='{ass_arg}'")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(frame), "-vf", vf, "-frames:v", "1", "-q:v", "2", str(out)])
    wide = out.with_name(out.stem + "_wide.jpg")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", "-q:v", "2", str(wide)])
    frame.unlink(missing_ok=True); ass_p.unlink(missing_ok=True)
    return out


# ----------------------------------------------------------------------------- review
def review(video: Path) -> Path:
    """Objective facts for Claude's QA pass: contact sheet (every ~2.5s), loudness, duration, black/freeze detection."""
    video = Path(video)
    out = video.parent / "review"
    out.mkdir(exist_ok=True)
    dur = duration(video)
    n = 30
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", f"fps={n / max(dur, 1):.4f},scale=216:384,tile=5x6",
          "-frames:v", "1", str(out / "contact.jpg")])
    ln = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", ln, re.S)
    loud = json.loads(m.group(0)) if m else {}
    bd = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-vf", "blackdetect=d=0.3,freezedetect=n=0.003:d=1.5",
                         "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    issues = [l.strip() for l in bd.splitlines() if "black_start" in l or "freeze_start" in l]
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,sample_rate",
                              "-of", "json", str(video)], capture_output=True, text=True).stdout
    ver = verify(video)
    rep = {"video": str(video), "duration_sec": round(dur, 2), "verify": ver, "loudness": {k: loud.get(k) for k in ("input_i", "input_tp", "input_lra")},
           "black_or_freeze": issues, "streams": json.loads(streams or "{}").get("streams"), "contact_sheet": str(out / "contact.jpg"),
           "checks": {"playable_everywhere": ver["ok"], "duration_ok_for_shorts": dur <= 180, "loudness_near_-14": bool(loud) and abs(float(loud.get("input_i", -99)) + 14) <= 2.5}}
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return out
