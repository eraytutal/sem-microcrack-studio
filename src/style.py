from __future__ import annotations

from pathlib import Path


def load_stylesheet() -> str:
    theme_path = Path(__file__).resolve().parent.parent / "assets" / "themes" / "dark.qss"
    return theme_path.read_text(encoding="utf-8")
