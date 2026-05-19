from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.annotation_io import get_dataset_status  # noqa: E402


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def collect_image_paths(folder_path: Path) -> list[str]:
    return [
        str(path)
        for path in sorted(folder_path.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]


def print_status(image_paths: Iterable[str]) -> None:
    status_data = get_dataset_status(list(image_paths))
    print(f"total images: {status_data['total_images']}")
    print(f"annotated: {status_data['annotated_images']}")
    print(f"no defect: {status_data['no_defect_images']}")
    print(f"unreviewed: {status_data['unreviewed_images']}")
    print()
    print("files:")

    rows = status_data.get("rows", [])
    if not isinstance(rows, list):
        return

    for row in rows:
        if not isinstance(row, dict):
            continue

        filename = row.get("filename", "")
        status = row.get("status", "Unreviewed")
        annotation_count = row.get("annotation_count", 0)
        print(f"- {filename}: {status}, annotations={annotation_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print Dataset Status Dashboard counts for an image folder without launching the GUI."
    )
    parser.add_argument("image_folder", help="Folder containing SEM image files.")
    return parser.parse_args()


def main() -> int:
    configure_output_encoding()
    args = parse_args()
    folder_path = Path(args.image_folder).expanduser()

    if not folder_path.exists():
        print(f"Image folder does not exist: {folder_path}", file=sys.stderr)
        return 1

    if not folder_path.is_dir():
        print(f"Image folder is not a directory: {folder_path}", file=sys.stderr)
        return 1

    print_status(collect_image_paths(folder_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
