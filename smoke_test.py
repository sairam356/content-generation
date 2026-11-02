"""Offline smoke test: mocked Gemini -> brief, synthetic audio through mastering, synthetic clips -> final.mp4.
No API keys or credits needed. Usage: python smoke_test.py
"""
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import analyze, voice, assemble

fake_analysis = {"title": "Why ice floats", "source_language": "en", "transcript_original": "...", "transcript_english": "...",
    "core_concept": "Ice is less dense than water", "hook": "q",
    "structure": [{"t_start": 0, "t_end": 3, "beat": "hook", "what_is_shown": "x", "what_is_said": "y"}],
    "presenter": {"on_camera": True, "framing": "mcu", "energy": "high", "setting": "kitchen"}, "visual_style": "clean",
    "animation_style": "motion graphics", "on_screen_text": ["ICE"], "key_images": ["glass"], "why_it_works": "curiosity",
    "facts_to_verify": ["density 0.92"]}
fake_script = {"title_te": "ఐస్ ఎందుకు తేలుతుంది?", "title_en": "Why ice floats", "hook_te": "h", "total_duration_sec": 15,
    "scenes": [
        {"id": 1, "type": "presenter", "duration_sec": 5, "narration_te": "ఐస్ నీటి మీద ఎందుకు తేలుతుందో తెలుసా? ఇది చూడండి.",
         "narration_en": "x", "delivery": "strong", "visual_prompt": "The exact man...", "on_screen_text_te": "ఐస్", "image_prompt": "portrait"},
        {"id": 2, "type": "broll", "duration_sec": 10, "narration_te": "నీరు గడ్డకట్టినప్పుడు దాని అణువులు దూరంగా జరుగుతాయి. అందుకే తక్కువ density.",
         "narration_en": "y", "delivery": "calm", "visual_prompt": "3d molecules", "on_screen_text_te": "", "image_prompt": "molecules"}],
    "cta_te": "ఫాలో చేయండి!", "caption_te": "c", "hashtags": ["#telugu"], "thumbnail_prompt": "t"}
calls = iter([fake_analysis, fake_script])
analyze._client = lambda: None
analyze._generate = lambda *a, **k: next(calls)
out = analyze.run("https://www.youtube.com/shorts/dQw4w9WgXcQ", name="smoke-test")
print(sorted(p.name for p in out.iterdir()))

def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)

for sid, secs in [(1, 3.2), (2, 7.5)]:
    raw = out / "audio" / f"scene_{sid}.raw.mp3"
    ff("-f", "lavfi", "-i", f"sine=f=180:d={secs}", "-c:a", "libmp3lame", str(raw))
    voice.enhance(raw, out / "audio" / f"scene_{sid}.wav", "deep")
ff("-f", "lavfi", "-i", "sine=f=200:d=2", "-c:a", "pcm_s16le", str(out / "audio" / "cta.wav"))

brief = json.loads((out / "brief.json").read_text(encoding="utf-8"))
for s in brief["script"]["scenes"]:
    d = voice.duration(out / "audio" / f"scene_{s['id']}.wav")
    s["audio_file"] = f"audio/scene_{s['id']}.wav"
    s["audio_duration_sec"] = round(d, 2)
    s["clip_duration_sec"] = 5 if d <= 4.6 else 10
brief["script"]["cta_audio_file"] = "audio/cta.wav"
(out / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")

ff("-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24:d=5", "-pix_fmt", "yuv420p", str(out / "clips" / "scene_1.mp4"))
ff("-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:d=5", "-f", "lavfi", "-i", "sine=f=440:d=5", "-shortest",
   "-pix_fmt", "yuv420p", str(out / "clips" / "scene_2.mp4"))
ff("-f", "lavfi", "-i", "color=c=blue:size=1080x1920:rate=30:d=2", "-pix_fmt", "yuv420p", str(out / "clips" / "cta.mp4"))

final = assemble.assemble(out)
print(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                      "-of", "compact", str(final)], capture_output=True, text=True).stdout)
ff("-ss", "1", "-i", str(final), "-frames:v", "1", "-vf", "scale=405:720", str(out / "frame_check.png"))
print("OK", final)
