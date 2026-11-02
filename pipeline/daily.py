"""Daily inspiration: pull the newest Shorts from the channels in channels.txt and brief each one.

Run by hand (`python -m pipeline daily`) or from Windows Task Scheduler (setup/register-daily-task.ps1).
Seen video ids are remembered in .state/seen.json so a video is only briefed once.
"""
import json
import subprocess
import sys
from datetime import date

from . import analyze, config

SEEN = config.STATE_DIR / "seen.json"


def _load_seen() -> dict:
    return json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}


def latest_shorts(channel: str, limit: int) -> list[dict]:
    url = channel.rstrip("/")
    if not url.endswith("/shorts"):
        url += "/shorts"
    cmd = ["yt-dlp", "--flat-playlist", "--playlist-end", str(limit), "--print", "%(id)s\t%(title)s", url]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print(f"[daily] yt-dlp failed for {channel}: {out.stderr.strip()[:200]}", file=sys.stderr)
        return []
    items = []
    for line in out.stdout.splitlines():
        if "\t" in line:
            vid, title = line.split("\t", 1)
            items.append({"id": vid, "title": title, "url": f"https://www.youtube.com/shorts/{vid}"})
    return items


def run(per_channel: int = 3, max_total: int = 3) -> list[str]:
    channels_file = config.ROOT / "channels.txt"
    channels = [l.strip() for l in channels_file.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
    if not channels:
        sys.exit("[daily] add channel URLs to channels.txt")
    seen = _load_seen()
    made = []
    for ch in channels:
        for short in latest_shorts(ch, per_channel):
            if short["id"] in seen or len(made) >= max_total:
                continue
            print(f"[daily] new short: {short['title']} ({short['url']})")
            try:
                out = analyze.run(short["url"])
                made.append(str(out))
                seen[short["id"]] = {"date": date.today().isoformat(), "project": out.name}
            except SystemExit as e:
                print(f"[daily] skipped {short['url']}: {e}", file=sys.stderr)
            config.STATE_DIR.mkdir(exist_ok=True)
            SEEN.write_text(json.dumps(seen, indent=2), encoding="utf-8")
    print(f"[daily] {len(made)} new brief(s): {made}")
    return made
