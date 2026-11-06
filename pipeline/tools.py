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
    chans = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
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
    wav = out.with_suffix(".16k.wav")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)])
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("[transcribe] faster-whisper missing: .venv\\Scripts\\pip install faster-whisper")
    model_name = config.env("WHISPER_MODEL", "small")
    print(f"[transcribe] whisper {model_name} on {media.name} ...")
    t0 = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(str(wav), language=language, word_timestamps=True, vad_filter=True,
                                  vad_parameters={"min_silence_duration_ms": 400})
    words, segments = [], []
    for s in segs:
        segments.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        for w in s.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)})
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
TELEPROMPTER_HTML = """<!doctype html><html lang="te"><head><meta charset="utf-8"><title>{title}</title>
<style>
 body{{margin:0;background:#000;color:#fff;font-family:"Nirmala UI","Noto Sans Telugu",sans-serif;overflow:hidden}}
 #bar{{position:fixed;top:0;left:0;right:0;padding:8px 14px;background:#111;font:14px system-ui;color:#aaa;z-index:9}}
 #bar b{{color:#fff}} #line{{position:fixed;top:40%;left:0;right:0;border-top:2px solid #e33;opacity:.5}}
 #txt{{padding:45vh 8vw 60vh;font-size:{size}px;line-height:1.55;font-weight:600}}
 .beat{{margin:0 0 1.2em}} .hook{{color:#ffd54a}} .cta{{color:#7fd3ff}} .cue{{font-size:.45em;color:#777;font-weight:400;display:block}}
 .mirror{{transform:scaleX(-1)}}
</style></head><body>
<div id="bar"><b>{title}</b> &nbsp; SPACE start/pause &nbsp; UP/DOWN speed &nbsp; R restart &nbsp; M mirror &nbsp; +/- font &nbsp; <span id="st">paused, speed <span id="sp">{speed}</span> px/s</span></div>
<div id="line"></div>
<div id="txt">{body}</div>
<script>
 let speed={speed},run=false,y=0,last=null,txt=document.getElementById('txt'),fs={size};
 function step(t){{ if(run){{ if(last!==null){{ y+= speed*(t-last)/1000; window.scrollTo(0,y);}} last=t; }} else last=null; requestAnimationFrame(step);}}
 requestAnimationFrame(step);
 document.addEventListener('keydown',e=>{{
  if(e.code==='Space'){{run=!run;e.preventDefault();}}
  if(e.code==='ArrowUp'){{speed+=10;}} if(e.code==='ArrowDown'){{speed=Math.max(10,speed-10);}}
  if(e.key==='r'||e.key==='R'){{y=0;window.scrollTo(0,0);run=false;}}
  if(e.key==='m'||e.key==='M'){{document.body.classList.toggle('mirror');}}
  if(e.key==='+'||e.key==='='){{fs+=4;txt.style.fontSize=fs+'px';}} if(e.key==='-'){{fs=Math.max(24,fs-4);txt.style.fontSize=fs+'px';}}
  document.getElementById('sp').textContent=speed; document.getElementById('st').firstChild.textContent=(run?'running':'paused')+', speed ';
 }});
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
    html = TELEPROMPTER_HTML.format(title=s.get("title_te", "Teleprompter"), body="\n".join(parts),
                                    speed=int(config.env("PROMPTER_SPEED", "55")), size=int(config.env("PROMPTER_FONT", "54")))
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

    def __call__(self, t: float) -> float:
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
        import urllib.parse
        import requests
        if not img.exists():
            r = requests.get("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full[:800]),
                             params={"width": 1080, "height": 1920, "nologo": "true"}, timeout=180)
            if r.status_code != 200:
                return None
            img.write_bytes(r.content)
    else:
        return None
    if raw.exists():
        _run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(raw), "-t", f"{seconds:.3f}", "-an",
              "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    else:
        frames = max(int(seconds * FPS), FPS)
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(img), "-vf",
              f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
              f"zoompan=z='min(zoom+{0.25 / frames:.6f},1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},format=yuv420p",
              "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    return out


def _presenter_segment(cut: Path, start: float, end: float, out: Path) -> Path:
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(cut), "-an",
          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(out)])
    return out


def _layout(bg: Path, pres: Path, layout: str, out: Path, accent: str, seconds: float) -> Path:
    """Composite presenter over/beside the background according to the layout template."""
    acc = accent.lstrip("#")
    if layout == "corner":
        fc = (f"[1:v]scale=460:-2[p];[0:v][p]overlay=x=40:y=H-h-300:shortest=1,format=yuv420p")
    elif layout == "circle-top":
        d = 560
        fc = (f"[1:v]crop='min(iw,ih*0.62)':'min(iw,ih*0.62)':(iw-ow)/2:ih*0.06,scale={d}:{d},format=rgba,"
              f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(pow(X-{d / 2},2)+pow(Y-{d / 2},2),pow({d / 2},2)),255,0)'[p];"
              f"color=c=0x{acc}:s={d + 24}x{d + 24},format=rgba,"
              f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(pow(X-{(d + 24) / 2},2)+pow(Y-{(d + 24) / 2},2),pow({(d + 24) / 2},2)),255,0)'[ring];"
              f"[0:v][ring]overlay=x=(W-w)/2:y=168:shortest=1[b1];[b1][p]overlay=x=(W-w)/2:y=180:shortest=1,format=yuv420p")
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
    clips = []
    for b in beats:
        s, e = remap(float(b["start"])), remap(float(b["end"]))
        if e - s < 0.3:
            continue
        kind = b.get("kind", "explain")
        pres = _presenter_segment(cut, s, e, work / f"pres_{b['id']}.mp4")
        print(f"[compose] beat {b['id']} ({kind}, {e - s:.1f}s)")
        if kind in ("hook", "cta") or layout == "full":
            clips.append(pres)
            continue
        bg = _broll(b, e - s + 0.5, work / f"bg_{b['id']}.mp4", style)
        if bg is None:
            clips.append(pres)
            continue
        clips.append(_layout(bg, pres, b.get("layout") or layout, work / f"beat_{b['id']}.mp4", accent, e - s))

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
        f"Style: Cap,{font},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,300,1",
        f"Style: CapHi,{font},64,&H00{accent[5:7]}{accent[3:5]}{accent[1:3]},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,300,1",
        f"Style: Title,{font},78,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,14,0,8,70,70,170,1",
        f"Style: Label,{font},52,&H00000000,&H00FFFFFF,&H00{accent[5:7]}{accent[3:5]}{accent[1:3]},&H00{accent[5:7]}{accent[3:5]}{accent[1:3]},-1,0,0,0,100,100,0,0,3,16,0,8,90,90,1040,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    title = plan.get("title_te")
    if title and beats:
        h0, h1 = remap(float(beats[0]["start"])), remap(float(beats[0]["end"]))
        ass.append(f"Dialogue: 2,{_ass_time(h0)},{_ass_time(min(h1, h0 + 4.0))},Title,,0,0,0,,{_esc(title)}")
    for b in beats:
        lab = (b.get("label_te") or "").strip()
        if lab and b.get("kind", "explain") not in ("hook", "cta"):
            ass.append(f"Dialogue: 1,{_ass_time(remap(float(b['start'])))},{_ass_time(remap(float(b['end'])))},Label,,0,0,0,,{_esc(lab)}")
        for c in b.get("captions", []):
            cs, ce = remap(float(c["start"])), remap(float(c["end"]))
            if ce - cs < 0.15:
                continue
            ass.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce - 0.03)},Cap,,0,0,0,,{_esc(c['text'])}")
    ass_path = work / "captions.ass"
    ass_path.write_text("\n".join(ass), encoding="utf-8")

    final = ready / f"{name}.mp4"
    ass_arg = ass_path.resolve().as_posix().replace(":", "\\:")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-i", str(cut)]
    af = config.env("VOICE_CHAIN", "highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=8:release=120:makeup=4,"
                                   "alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11")
    music = plan.get("music")
    fc = f"[0:v]subtitles='{ass_arg}'[v];[1:a]{af}[voice]"
    if music:
        mpath = Path(music) if Path(music).is_absolute() else config.ROOT / music
        cmd += ["-stream_loop", "-1", "-i", str(mpath)]
        fc += f";[2:a]volume={float(plan.get('music_volume', 0.08))}[m];[voice][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
    else:
        fc += ";[voice]anull[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{remap.total:.3f}", "-c:v", "libx264",
            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(final)]
    _run(cmd)

    thumb_at = float(plan.get("thumbnail_sec", remap(float(beats[0]["start"])) + 0.8 if beats else 1.0))
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{thumb_at:.2f}", "-i", str(final), "-frames:v", "1", str(ready / f"{name}.jpg")])
    meta = [f"# {plan.get('title_te', name)}", "", plan.get("description_te", ""), "",
            " ".join(plan.get("hashtags", [])), "", f"Duration: {duration(final):.1f}s  Layout: {layout}",
            "Label at upload: 'Altered or synthetic content' = YES only if AI b-roll is used (it is, when backgrounds are generated)."]
    (ready / f"{name}.md").write_text("\n".join(meta), encoding="utf-8")
    print(f"[compose] ready: {final}  ({duration(final):.1f}s)")
    print(final)
    return final


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
    rep = {"video": str(video), "duration_sec": round(dur, 2), "loudness": {k: loud.get(k) for k in ("input_i", "input_tp", "input_lra")},
           "black_or_freeze": issues, "streams": json.loads(streams or "{}").get("streams"), "contact_sheet": str(out / "contact.jpg"),
           "checks": {"duration_ok_for_shorts": dur <= 180, "loudness_near_-14": bool(loud) and abs(float(loud.get("input_i", -99)) + 14) <= 2.5}}
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return out
