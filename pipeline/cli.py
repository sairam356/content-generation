import argparse
import sys

from . import config


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m pipeline",
                                description="Telugu Shorts studio tools (Claude Code does the thinking; these are its hands)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Gemini: watch a Short, write brief.json + Telugu scene script")
    a.add_argument("url")
    a.add_argument("--name", help="project folder name (default: date-title-videoid)")
    a.add_argument("--target-sec", type=int, help="narration budget in seconds (default TARGET_DURATION_SEC)")
    a.add_argument("--mode", choices=["replicate", "remix"], help="replicate = same transcript/shots/timing with your face+voice (default); remix = original re-explanation")

    v = sub.add_parser("voice", help="ElevenLabs voice management")
    vs = v.add_subparsers(dest="vcmd", required=True)
    vc = vs.add_parser("clone", help="clone your voice from assets/me/voice/*")
    vc.add_argument("--name", default="me")
    vd = vs.add_parser("design", help="design a deep presenter voice (alternative to your clone)")
    vd.add_argument("--description")
    vd.add_argument("--text")
    vds = vs.add_parser("design-save", help="save design preview N as a voice")
    vds.add_argument("n", type=int)
    vds.add_argument("--name", default="presenter-deep")
    vp = vs.add_parser("preview", help="speak one Telugu line with the current voice + preset")
    vp.add_argument("--text")
    vp.add_argument("--voice-id")
    vp.add_argument("--preset", choices=["deep", "clean", "none"])

    t = sub.add_parser("tts", help="ElevenLabs: narration wav per scene in your cloned voice (Telugu)")
    t.add_argument("project")
    t.add_argument("--voice-id")
    t.add_argument("--preset", choices=["deep", "clean", "none"])
    t.add_argument("--force", action="store_true")

    e = sub.add_parser("enhance", help="apply a mastering preset to any audio file")
    e.add_argument("src")
    e.add_argument("dst")
    e.add_argument("--preset", default="deep", choices=["deep", "clean", "none"])

    s = sub.add_parser("assemble", help="ffmpeg: clips + narration + captions -> final.mp4")
    s.add_argument("project")
    s.add_argument("--music", help="background music file (mixed at low volume)")
    s.add_argument("--no-subs", action="store_true")

    sub.add_parser("channels", help="recent Shorts titles/views for every channel in channels.txt -> .state/channels.json").add_argument("--limit", type=int, default=15)
    sub.add_parser("inspect", help="download a reference Short -> meta/transcript/frames for Claude (no Gemini)").add_argument("url")
    sub.add_parser("teleprompter", help="script.json -> teleprompter.html").add_argument("script")
    tr = sub.add_parser("transcribe", help="recording -> words.json (faster-whisper word timings + silences)")
    tr.add_argument("media")
    tr.add_argument("--out")
    tr.add_argument("--lang", default="te")
    sub.add_parser("compose", help="plan.json -> ready/<name>.mp4 + thumbnail + metadata").add_argument("plan")
    sub.add_parser("review", help="QA facts for a video: contact sheet, loudness, black/freeze, streams").add_argument("video")

    d = sub.add_parser("daily", help="brief the newest Shorts from channels.txt")
    d.add_argument("--per-channel", type=int, default=3)
    d.add_argument("--max-total", type=int, default=3)

    args = p.parse_args(argv)

    if args.cmd == "analyze":
        from . import analyze
        out = analyze.run(args.url, args.name, args.target_sec, args.mode)
        print(out)
    elif args.cmd == "voice":
        from . import voice
        if args.vcmd == "clone":
            voice.clone(args.name)
        elif args.vcmd == "design":
            voice.design(args.description, args.text)
        elif args.vcmd == "design-save":
            voice.design_save(args.n, args.name)
        elif args.vcmd == "preview":
            voice.preview(args.text, args.voice_id, args.preset)
    elif args.cmd == "tts":
        from . import voice
        voice.tts_project(config.project_dir(args.project), args.voice_id, args.preset, args.force)
    elif args.cmd == "enhance":
        from pathlib import Path
        from . import voice
        voice.enhance(Path(args.src), Path(args.dst), args.preset)
    elif args.cmd == "assemble":
        from . import assemble
        assemble.assemble(config.project_dir(args.project), args.music, args.no_subs)
    elif args.cmd in ("channels", "inspect", "teleprompter", "transcribe", "compose", "review"):
        from pathlib import Path
        from . import tools
        if args.cmd == "channels":
            tools.channels(args.limit)
        elif args.cmd == "inspect":
            tools.inspect(args.url)
        elif args.cmd == "teleprompter":
            tools.teleprompter(Path(args.script))
        elif args.cmd == "transcribe":
            tools.transcribe(Path(args.media), Path(args.out) if args.out else None, args.lang or None)
        elif args.cmd == "compose":
            tools.compose(Path(args.plan))
        elif args.cmd == "review":
            tools.review(Path(args.video))
    elif args.cmd == "daily":
        from . import daily
        daily.run(args.per_channel, args.max_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
