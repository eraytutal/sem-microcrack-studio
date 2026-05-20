from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QImageReader

from src.annotation_model import normalize_annotation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "exports" / "yolo_seg"
DEFAULT_CLASS_MAP = {
    "crack": 0,
    "scratch": 1,
    "pit": 2,
    "void": 3,
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
SPLITS = ("train", "val", "test")


def rectangle_bbox_to_polygon_points(bbox: list[object]) -> list[list[float]] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None

    try:
        x, y, width, height = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None

    return [
        [x, y],
        [x + width, y],
        [x + width, y + height],
        [x, y + height],
    ]


def normalize_points(points: list[list[object]], width: int, height: int) -> list[float] | None:
    if width <= 0 or height <= 0 or not isinstance(points, list) or len(points) < 3:
        return None

    normalized: list[float] = []
    for point in points:
        if not isinstance(point, list) or len(point) < 2:
            return None
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            return None
        normalized.extend([_clamp(x / width), _clamp(y / height)])
    return normalized


def annotation_to_yolo_seg_line(
    annotation: dict[str, Any],
    width: int,
    height: int,
    class_map: dict[str, int],
) -> tuple[str | None, dict[str, int]]:
    counters = _zero_annotation_counters()
    raw_label = str(annotation.get("label") or "")
    label = raw_label.strip()
    if label == "uncertain" and label not in class_map:
        counters["skipped_uncertain"] += 1
        return None, counters
    if label not in class_map:
        counters["skipped_labels_not_in_class_map"] += 1
        return None, counters
    if str(annotation.get("status") or "") != "verified":
        counters["skipped_not_exportable"] += 1
        return None, counters
    if not bool(annotation.get("exportable_to_mask", True)):
        counters["skipped_not_exportable"] += 1
        return None, counters

    shape_type = str(annotation.get("shape_type") or "").lower()
    points: list[list[object]] | None
    if shape_type == "polygon" or annotation.get("points"):
        points = annotation.get("points", [])
        if not isinstance(points, list) or len(points) < 3:
            counters["skipped_invalid_geometry"] += 1
            return None, counters
        counters["polygons_exported"] += 1
    else:
        points = rectangle_bbox_to_polygon_points(annotation.get("bbox", []))
        if points is None:
            counters["skipped_invalid_geometry"] += 1
            return None, counters
        counters["rectangles_converted_to_polygons"] += 1

    normalized = normalize_points(points, width, height)
    if normalized is None:
        counters["skipped_invalid_geometry"] += 1
        counters["polygons_exported"] = 0
        counters["rectangles_converted_to_polygons"] = 0
        return None, counters

    values = " ".join(_format_number(value) for value in normalized)
    return f"{class_map[label]} {values}", counters


def collect_exportable_images(
    image_folder: str | Path,
    annotations_dir: str | Path,
    class_map: dict[str, int] | None = None,
    include_no_defect: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    class_map = class_map or dict(DEFAULT_CLASS_MAP)
    image_paths = _collect_image_paths(image_folder)
    report = _empty_report()
    report["total_images_seen"] = len(image_paths)

    records: list[dict[str, Any]] = []
    for image_path in image_paths:
        annotation_path = Path(annotations_dir) / f"{image_path.stem}.json"
        if not annotation_path.exists():
            report["skipped_unreviewed"] += 1
            continue

        data = _load_json(annotation_path)
        if not data:
            report["skipped_unreviewed"] += 1
            continue

        report["annotation_files_read"] += 1
        raw_annotations = data.get("annotations", [])
        annotations = _normalized_annotations(raw_annotations)
        image_status = str(data.get("image_status") or "")
        if not image_status:
            image_status = "annotated" if annotations else "unreviewed"

        width, height = _image_size(image_path, data)
        lines: list[str] = []
        class_counts: dict[str, int] = {}
        record_counts = _zero_annotation_counters()

        for annotation in annotations:
            line, counters = annotation_to_yolo_seg_line(annotation, width, height, class_map)
            _add_counters(record_counts, counters)
            if line is None:
                continue
            lines.append(line)
            label = str(annotation.get("label") or "")
            class_counts[label] = class_counts.get(label, 0) + 1

        _add_counters(report, record_counts)
        if lines:
            records.append(
                {
                    "image_path": image_path,
                    "width": width,
                    "height": height,
                    "label_lines": lines,
                    "class_counts": class_counts,
                    "is_no_defect": False,
                }
            )
            continue

        if image_status == "reviewed_no_defect" and not annotations and include_no_defect:
            report["no_defect_images_exported"] += 1
            records.append(
                {
                    "image_path": image_path,
                    "width": width,
                    "height": height,
                    "label_lines": [],
                    "class_counts": {},
                    "is_no_defect": True,
                }
            )
        elif image_status == "unreviewed" and not annotations:
            report["skipped_unreviewed"] += 1

    return records, report


def split_images(
    image_records: list[dict[str, Any]],
    train_percent: int = 70,
    val_percent: int = 20,
    test_percent: int = 10,
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    _validate_split(train_percent, val_percent, test_percent)
    shuffled = list(image_records)
    random.Random(seed).shuffle(shuffled)
    count = len(shuffled)
    split_counts = _split_counts(count, train_percent, val_percent, test_percent)
    train_end = split_counts["train"]
    val_end = train_end + split_counts["val"]
    return {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }


def export_yolo_seg_dataset(
    image_folder: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    annotations_dir: str | Path | None = None,
    train_percent: int = 70,
    val_percent: int = 20,
    test_percent: int = 10,
    seed: int = 42,
    include_no_defect: bool = True,
    include_uncertain: bool = False,
    class_map: dict[str, int] | None = None,
    clear_output: bool = True,
) -> dict[str, Any]:
    annotations_root = Path(annotations_dir) if annotations_dir else PROJECT_ROOT / "data" / "annotations"
    output_root = Path(output_dir)
    export_class_map = dict(class_map or DEFAULT_CLASS_MAP)
    if include_uncertain and "uncertain" not in export_class_map:
        export_class_map["uncertain"] = max(export_class_map.values(), default=-1) + 1

    records, report = collect_exportable_images(
        image_folder,
        annotations_root,
        export_class_map,
        include_no_defect,
    )
    split_records = split_images(records, train_percent, val_percent, test_percent, seed)

    if clear_output:
        _clear_generated_output(output_root)
    _create_output_dirs(output_root)

    for split_name, split_items in split_records.items():
        for record in split_items:
            image_path = Path(record["image_path"])
            target_image = output_root / "images" / split_name / image_path.name
            target_label = output_root / "labels" / split_name / f"{image_path.stem}.txt"
            shutil.copy2(image_path, target_image)
            label_lines = record.get("label_lines", [])
            target_label.write_text("\n".join(label_lines) + ("\n" if label_lines else ""), encoding="utf-8")
            _update_split_report(report, split_name, record)

    report["images_exported"] = len(records)
    report["labels_written"] = sum(len(record["label_lines"]) for record in records)
    report["empty_label_files_written"] = sum(1 for record in records if not record["label_lines"])

    write_data_yaml(output_root, export_class_map)
    write_export_report(output_root, report)
    return report


def write_data_yaml(output_dir: str | Path, class_map: dict[str, int]) -> Path:
    output_root = Path(output_dir)
    names = {class_id: label for label, class_id in class_map.items()}
    lines = [
        f"path: {output_root.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    for class_id in sorted(names):
        lines.append(f"  {class_id}: {names[class_id]}")

    data_yaml = output_root / "data.yaml"
    data_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data_yaml


def write_export_report(output_dir: str | Path, report: dict[str, Any]) -> Path:
    report_path = Path(output_dir) / "export_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report_path


def _collect_image_paths(image_folder: str | Path) -> list[Path]:
    root = Path(image_folder)
    if not root.exists():
        raise ValueError(f"Image folder does not exist: {root}")
    return [
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _normalized_annotations(raw_annotations: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_annotations, list):
        return []
    return [
        normalize_annotation(annotation, fallback_id=f"ann_{index:03d}")
        for index, annotation in enumerate(raw_annotations, start=1)
        if isinstance(annotation, dict)
    ]


def _image_size(image_path: Path, data: dict[str, Any]) -> tuple[int, int]:
    size = _read_image_size(image_path)
    if size.isValid() and size.width() > 0 and size.height() > 0:
        return size.width(), size.height()

    image_data = data.get("image", {})
    if isinstance(image_data, dict):
        try:
            width = int(image_data.get("width", 0))
            height = int(image_data.get("height", 0))
        except (TypeError, ValueError):
            width = 0
            height = 0
        if width > 0 and height > 0:
            return width, height

    raise ValueError(f"Could not determine image size for {image_path}")


def _read_image_size(image_path: Path) -> QSize:
    reader = QImageReader(str(image_path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        return size

    image = reader.read()
    return image.size() if not image.isNull() else QSize()


def _validate_split(train_percent: int, val_percent: int, test_percent: int) -> None:
    if train_percent < 0 or val_percent < 0 or test_percent < 0:
        raise ValueError("Split percentages must be non-negative.")
    if train_percent + val_percent + test_percent != 100:
        raise ValueError("Train, val, and test percentages must sum to 100.")


def _split_counts(count: int, train_percent: int, val_percent: int, test_percent: int) -> dict[str, int]:
    raw = {
        "train": count * train_percent / 100,
        "val": count * val_percent / 100,
        "test": count * test_percent / 100,
    }
    counts = {split: int(value) for split, value in raw.items()}
    remaining = count - sum(counts.values())
    fractions = sorted(
        ((raw[split] - counts[split], split) for split in SPLITS),
        key=lambda item: (-item[0], SPLITS.index(item[1])),
    )
    for _, split in fractions[:remaining]:
        counts[split] += 1
    return counts


def _create_output_dirs(output_dir: Path) -> None:
    for split_name in SPLITS:
        (output_dir / "images" / split_name).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split_name).mkdir(parents=True, exist_ok=True)


def _clear_generated_output(output_dir: Path) -> None:
    for child_name in ("images", "labels"):
        child = output_dir / child_name
        if child.exists():
            shutil.rmtree(child)
    for filename in ("data.yaml", "export_report.json"):
        file_path = output_dir / filename
        if file_path.exists():
            file_path.unlink()


def _empty_report() -> dict[str, Any]:
    return {
        "total_images_seen": 0,
        "images_exported": 0,
        "annotation_files_read": 0,
        "labels_written": 0,
        "empty_label_files_written": 0,
        "rectangles_converted_to_polygons": 0,
        "polygons_exported": 0,
        "no_defect_images_exported": 0,
        "skipped_unreviewed": 0,
        "skipped_uncertain": 0,
        "skipped_invalid_geometry": 0,
        "skipped_not_exportable": 0,
        "skipped_labels_not_in_class_map": 0,
        "split": {
            "train": {"images": 0, "annotations": 0, "classes": {}},
            "val": {"images": 0, "annotations": 0, "classes": {}},
            "test": {"images": 0, "annotations": 0, "classes": {}},
        },
    }


def _zero_annotation_counters() -> dict[str, int]:
    return {
        "rectangles_converted_to_polygons": 0,
        "polygons_exported": 0,
        "skipped_uncertain": 0,
        "skipped_invalid_geometry": 0,
        "skipped_not_exportable": 0,
        "skipped_labels_not_in_class_map": 0,
    }


def _add_counters(target: dict[str, Any], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = int(target.get(key, 0)) + value


def _update_split_report(report: dict[str, Any], split_name: str, record: dict[str, Any]) -> None:
    split_report = report["split"][split_name]
    split_report["images"] += 1
    annotations = len(record.get("label_lines", []))
    split_report["annotations"] += annotations
    for label, count in record.get("class_counts", {}).items():
        classes = split_report["classes"]
        classes[label] = classes.get(label, 0) + count


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _format_number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"
