import argparse
import sys

from . import config


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m pipeline",
                                description="YouTube Short -> Telugu AI-presenter Short (Gemini + ElevenLabs + Higgsfield)")
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
    elif args.cmd == "daily":
        from . import daily
        daily.run(args.per_channel, args.max_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
