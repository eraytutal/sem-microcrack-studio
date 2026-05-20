from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ANNOTATIONS_DIR = DATA_DIR / "annotations"
PREDICTIONS_DIR = DATA_DIR / "predictions"
EXPORTS_DIR = DATA_DIR / "exports"


def ensure_app_data_dirs() -> None:
    """Create generated-data directories needed by the demo workflows."""
    for directory in (DATA_DIR, ANNOTATIONS_DIR, PREDICTIONS_DIR, EXPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
