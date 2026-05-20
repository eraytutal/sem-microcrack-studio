from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.yolo_seg_export import DEFAULT_OUTPUT_DIR, export_yolo_seg_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export confirmed annotations to a YOLO segmentation dataset.")
    parser.add_argument("--image-dir", required=True, help="Source image folder.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output folder. Defaults to data/exports/yolo_seg.",
    )
    parser.add_argument("--annotations-dir", default=None, help="Annotation JSON folder.")
    parser.add_argument("--train", type=int, default=70, help="Train split percentage.")
    parser.add_argument("--val", type=int, default=20, help="Validation split percentage.")
    parser.add_argument("--test", type=int, default=10, help="Test split percentage.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic shuffle seed.")
    parser.add_argument(
        "--exclude-no-defect",
        action="store_true",
        help="Do not export reviewed_no_defect images as negative samples.",
    )
    parser.add_argument(
        "--include-uncertain",
        action="store_true",
        help="Include uncertain as an export class.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = export_yolo_seg_dataset(
            image_folder=args.image_dir,
            output_dir=args.output_dir,
            annotations_dir=args.annotations_dir,
            train_percent=args.train,
            val_percent=args.val,
            test_percent=args.test,
            seed=args.seed,
            include_no_defect=not args.exclude_no_defect,
            include_uncertain=args.include_uncertain,
        )
    except Exception as error:
        print(f"YOLO segmentation export failed: {error}", file=sys.stderr)
        return 1

    print(f"YOLO segmentation dataset written to: {Path(args.output_dir).resolve()}")
    print(f"Images exported: {report['images_exported']}")
    print(f"Labels written: {report['labels_written']}")
    print(f"No Defect negatives: {report['no_defect_images_exported']}")
    print(f"Skipped unreviewed: {report['skipped_unreviewed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
