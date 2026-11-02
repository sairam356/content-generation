import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
ASSETS_DIR = ROOT / "assets" / "me"
STATE_DIR = ROOT / ".state"

load_dotenv(ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip() or default


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        sys.exit(f"[config] {name} is not set. Copy .env.example to .env and fill it in.")
    return value


def slugify(text: str, max_len: int = 48) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "short"


def youtube_id(url: str) -> str:
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not m:
        sys.exit(f"[config] Not a recognisable YouTube URL: {url}")
    return m.group(1)


def project_dir(name: str) -> Path:
    p = Path(name)
    if not p.is_absolute() and not p.exists():
        p = PROJECTS_DIR / name
    if not (p / "brief.json").exists():
        sys.exit(f"[config] No brief.json in {p}. Run `python -m pipeline analyze <url>` first.")
    return p
