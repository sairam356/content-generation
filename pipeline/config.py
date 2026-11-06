import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / ".state"

load_dotenv(ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip() or default


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        sys.exit(f"[config] {name} is not set. Copy .env.example to .env and fill it in.")
    return value


def youtube_id(url: str) -> str:
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not m:
        sys.exit(f"[config] Not a recognisable YouTube URL: {url}")
    return m.group(1)
