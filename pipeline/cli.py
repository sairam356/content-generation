"""Claude Code does the thinking; these commands are its hands. See CLAUDE.md."""
import argparse
import sys
from pathlib import Path


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m pipeline", description="Telugu Shorts Studio tools")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("channels", help="recent Shorts per channel in channels.txt -> .state/channels.json").add_argument("--limit", type=int, default=15)
    sub.add_parser("watch", help="Gemini watches a Short -> .state/refs/<id>/analysis.json").add_argument("url")
    sub.add_parser("inspect", help="download a Short -> meta.json, transcript.json, frames.jpg (no Gemini)").add_argument("url")
    sub.add_parser("teleprompter", help="script.json -> teleprompter.html").add_argument("script")
    t = sub.add_parser("transcribe", help="recording -> words.json (faster-whisper word timings + silences)")
    t.add_argument("media"); t.add_argument("--out"); t.add_argument("--lang", default="te")
    sub.add_parser("compose", help="plan.json -> ready/<name>.mp4 + .jpg + .md").add_argument("plan")
    sub.add_parser("review", help="QA facts for a video -> review/report.json + contact.jpg").add_argument("video")
    sub.add_parser("verify", help="prove an mp4 is complete + plays everywhere (full decode); exit 1 if not").add_argument("video")
    a = p.parse_args(argv)
    from . import tools
    if a.cmd == "channels":
        tools.channels(a.limit)
    elif a.cmd == "watch":
        from . import watch
        watch.watch(a.url)
    elif a.cmd == "inspect":
        tools.inspect(a.url)
    elif a.cmd == "teleprompter":
        tools.teleprompter(Path(a.script))
    elif a.cmd == "transcribe":
        tools.transcribe(Path(a.media), Path(a.out) if a.out else None, a.lang or None)
    elif a.cmd == "compose":
        tools.compose(Path(a.plan))
    elif a.cmd == "review":
        tools.review(Path(a.video))
    elif a.cmd == "verify":
        import json
        rep = tools.verify(Path(a.video))
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        sys.exit(0 if rep["ok"] else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
