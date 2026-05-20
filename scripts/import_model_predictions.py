from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model_prediction_import import (  # noqa: E402
    DEFAULT_CLASS_MAP,
    import_prediction_folder,
    import_prediction_txt,
    summarize_import_results,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import model prediction txt files into SEM Studio JSON.")
    parser.add_argument("--image", help="Path to a single image.")
    parser.add_argument("--labels", help="Path to a single prediction label .txt file.")
    parser.add_argument("--image-dir", help="Path to an image folder.")
    parser.add_argument("--label-dir", help="Path to a label .txt folder.")
    parser.add_argument("--output-dir", default=None, help="Output directory for prediction JSON files.")
    parser.add_argument(
        "--class-map-json",
        default=None,
        help="Optional JSON object mapping class ids to labels.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    class_map = dict(DEFAULT_CLASS_MAP)
    if args.class_map_json:
        try:
            class_map.update(json.loads(args.class_map_json))
        except json.JSONDecodeError as error:
            print(f"Invalid --class-map-json: {error}", file=sys.stderr)
            return 2

    output_dir = args.output_dir if args.output_dir else None
    try:
        if args.image and args.labels:
            result = import_prediction_txt(
                args.image,
                args.labels,
                class_map,
                output_dir=output_dir or PROJECT_ROOT / "data" / "predictions",
            )
            _print_result(result)
            return 0

        if args.image_dir and args.label_dir:
            results = import_prediction_folder(
                args.image_dir,
                args.label_dir,
                class_map,
                output_dir=output_dir or PROJECT_ROOT / "data" / "predictions",
            )
            for result in results:
                _print_result(result)
            _print_summary(summarize_import_results(results))
            return 0
    except Exception as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1

    print("Provide either --image with --labels, or --image-dir with --label-dir.", file=sys.stderr)
    return 2


def _print_result(result: dict) -> None:
    image = result.get("image", {})
    predictions = result.get("predictions", [])
    print(f"{image.get('filename', 'image')}: imported {len(predictions)} predictions -> {result.get('output_path')}")
    for warning in result.get("warnings", []):
        print(f"  warning: {warning}")


def _print_summary(summary: dict) -> None:
    print(f"Images processed: {summary.get('images_processed', 0)}")
    print(f"Prediction files found: {summary.get('prediction_files_found', 0)}")
    print(f"Imported predictions: {summary.get('imported_predictions', 0)}")
    print(f"Empty label files: {summary.get('empty_label_files', 0)}")
    print(f"Missing label files: {summary.get('missing_label_files', 0)}")
    print(f"Unmatched label files ignored: {summary.get('unmatched_label_files', 0)}")
    print(f"Invalid lines skipped: {summary.get('invalid_lines_skipped', 0)}")


if __name__ == "__main__":
    raise SystemExit(main())
