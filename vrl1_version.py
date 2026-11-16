"""Single version source: VERSION.md at repo root. Never hardcode versions."""
from pathlib import Path


def app_version() -> str:
    p = Path(__file__).resolve().parent / "VERSION.md"
    try:
        return p.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"
