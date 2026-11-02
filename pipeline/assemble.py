"""Step 4: stitch the Higgsfield clips + narration into a 1080x1920 Short with Telugu captions (ffmpeg).

Input: project/timeline.json written by Claude after generating clips:
  {"items": [{"scene_id": 1, "video": "clips/scene_1.mp4", "audio": "audio/scene_1.wav",
              "use_clip_audio": false}, ...],
   "music": "assets/music/bed.mp3" (optional), "burn_subtitles": true}
If timeline.json is missing, one is derived from brief.json (clips/scene_<id>.mp4 + audio/scene_<id>.wav).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

W, H = 1080, 1920


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _probe(path: Path, stream: str, key: str) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", f"stream={key}",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return out.stdout.strip()


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def default_timeline(project: Path) -> dict:
    brief = json.loads((project / "brief.json").read_text(encoding="utf-8"))
    items = []
    for s in brief["script"]["scenes"]:
        video = project / "clips" / f"scene_{s['id']}.mp4"
        if not video.exists():
            print(f"[assemble] missing {video}, skipping scene {s['id']}")
            continue
        items.append({"scene_id": s["id"], "video": f"clips/scene_{s['id']}.mp4",
                      "audio": s.get("audio_file"), "use_clip_audio": False,
                      "text": s.get("on_screen_text_te", ""), "narration_te": s["narration_te"]})
    cta_clip = project / "clips" / "cta.mp4"
    if cta_clip.exists():
        items.append({"scene_id": "cta", "video": "clips/cta.mp4", "audio": brief["script"].get("cta_audio_file"),
                      "use_clip_audio": False, "text": "", "narration_te": brief["script"].get("cta_te", "")})
    return {"items": items, "burn_subtitles": True}


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _chunks(text: str, max_words: int = 4) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)] or [text]


def write_srt(items: list[dict], durations: list[float], path: Path) -> Path:
    """Short caption chunks (4 words) spread evenly over each scene - good enough without word timestamps."""
    t, n, lines = 0.0, 1, []
    for item, dur in zip(items, durations):
        text = item.get("narration_te") or ""
        chunks = _chunks(text) if text else []
        if chunks:
            per = dur / len(chunks)
            for i, chunk in enumerate(chunks):
                lines += [str(n), f"{_srt_time(t + i * per)} --> {_srt_time(t + (i + 1) * per - 0.05)}", chunk, ""]
                n += 1
        t += dur
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def normalize_scene(project: Path, item: dict, out: Path) -> float:
    """Scale/pad to 1080x1920, replace audio with the narration, match the length to the narration."""
    video = project / item["video"]
    audio = project / item["audio"] if item.get("audio") else None
    vdur = _duration(video)
    target = _duration(audio) if audio and not item.get("use_clip_audio") else vdur
    target = max(target, 1.0)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,format=yuv420p,"
          f"tpad=stop_mode=clone:stop_duration={max(0.0, target - vdur) + 0.2:.3f}")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    if audio and not item.get("use_clip_audio"):
        cmd += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        has_audio = bool(_probe(video, "a", "codec_type"))
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-map", "0:v:0", "-map", "1:a:0"]
    cmd += ["-vf", vf, "-t", f"{target:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
    _run(cmd)
    return target


def assemble(project: Path, music: str | None = None, no_subs: bool = False) -> Path:
    if not shutil.which("ffmpeg"):
        sys.exit("[assemble] ffmpeg not found on PATH")
    tl_path = project / "timeline.json"
    timeline = json.loads(tl_path.read_text(encoding="utf-8")) if tl_path.exists() else default_timeline(project)
    items = timeline["items"]
    if not items:
        sys.exit("[assemble] no clips to assemble (expected project/clips/scene_<id>.mp4)")
    if not tl_path.exists():
        tl_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    build = project / "build"
    build.mkdir(exist_ok=True)
    norm, durations = [], []
    for item in items:
        out = build / f"norm_{item['scene_id']}.mp4"
        print(f"[assemble] scene {item['scene_id']} -> {out.name}")
        durations.append(normalize_scene(project, item, out))
        norm.append(out)

    concat_list = build / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in norm), encoding="utf-8")
    joined = build / "joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
          "-c", "copy", str(joined)])

    final = project / "final.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined)]
    filters = []
    music = music or timeline.get("music")
    if music:
        mpath = (config.ROOT / music) if not Path(music).is_absolute() else Path(music)
        cmd += ["-stream_loop", "-1", "-i", str(mpath)]
        filters.append("[1:a]volume=0.12[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]")
    if not no_subs and timeline.get("burn_subtitles", True):
        srt = write_srt(items, durations, build / "captions.srt")
        font = config.env("SUBTITLE_FONT", "Nirmala UI")
        style = (f"FontName={font},FontSize=15,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                 "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=330")
        srt_arg = srt.resolve().as_posix().replace(":", "\\:")
        filters.append(f"[0:v]subtitles='{srt_arg}':force_style='{style}'[v]")
    if filters:
        cmd += ["-filter_complex", ";".join(filters)]
        cmd += ["-map", "[v]" if any(f.endswith("[v]") for f in filters) else "0:v"]
        cmd += ["-map", "[a]" if music else "0:a"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(final)]
    _run(cmd)
    print(f"[assemble] final short: {final}  ({sum(durations):.1f}s)")
    return final
