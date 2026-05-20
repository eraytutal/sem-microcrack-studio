from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QImageReader

from src.annotation_model import calculate_bbox_from_points
from src.prediction_io import PREDICTIONS_DIR


DEFAULT_CLASS_MAP = {
    "0": "crack",
    "1": "scratch",
    "2": "pit",
    "3": "void",
    "4": "uncertain",
}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def parse_yolo_seg_line(
    line: str,
    image_width: int,
    image_height: int,
    class_map: dict,
) -> dict[str, Any] | None:
    tokens = line.strip().lstrip("\ufeff").split()
    if len(tokens) < 7:
        return None

    class_id = _normalize_class_id(tokens[0])
    try:
        values = [float(token) for token in tokens[1:]]
    except ValueError:
        return None

    confidence: float | None = None
    coordinate_values = values
    if len(values) % 2 == 1:
        confidence = values[-1]
        coordinate_values = values[:-1]

    if len(coordinate_values) == 4:
        return None

    if len(coordinate_values) < 6 or len(coordinate_values) % 2 != 0:
        return None

    points: list[list[float]] = []
    for x_value, y_value in zip(coordinate_values[0::2], coordinate_values[1::2]):
        if not 0.0 <= x_value <= 1.0 or not 0.0 <= y_value <= 1.0:
            return None
        points.append([x_value * image_width, y_value * image_height])

    if len(points) < 3:
        return None

    return {
        "label": _label_for_class_id(class_id, class_map),
        "shape_type": "polygon",
        "points": points,
        "bbox": calculate_bbox_from_points(points),
        "source": "model_import",
        "confidence": confidence,
        "status": "pending",
    }


def import_prediction_txt(
    image_path: str | Path,
    label_txt_path: str | Path,
    class_map: dict,
    output_dir: str | Path = PREDICTIONS_DIR,
) -> dict[str, Any]:
    image = Path(image_path)
    label_file = Path(label_txt_path)
    output_path = Path(output_dir) / f"{image.stem}.json"
    image_size = _read_image_size(image)
    warnings: list[str] = []
    predictions: list[dict[str, Any]] = []
    summary = {
        "images_processed": 1,
        "prediction_files_found": 0,
        "imported_predictions": 0,
        "empty_label_files": 0,
        "missing_label_files": 0,
        "unmatched_label_files": 0,
        "invalid_lines_skipped": 0,
    }

    if not label_file.exists():
        summary["missing_label_files"] = 1
        warnings.append(f"Label file does not exist: {label_file}")
    else:
        summary["prediction_files_found"] = 1
        try:
            lines = label_file.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            lines = []
            warnings.append(f"Could not read label file: {error}")

        non_empty_lines = [line for line in lines if line.strip()]
        if not non_empty_lines:
            summary["empty_label_files"] = 1

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            prediction = parse_yolo_seg_line(stripped, image_size.width(), image_size.height(), class_map)
            if prediction is None:
                summary["invalid_lines_skipped"] += 1
                warnings.append(f"Skipped invalid or unsupported line {line_number}: {stripped}")
                continue

            prediction["id"] = f"pred_{len(predictions) + 1:03d}"
            predictions.append(prediction)

    summary["imported_predictions"] = len(predictions)
    payload = {
        "image": {
            "filename": image.name,
            "path": str(image.resolve()).replace("\\", "/"),
            "width": image_size.width(),
            "height": image_size.height(),
        },
        "predictions": predictions,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")

    return {
        **payload,
        "output_path": str(output_path),
        "warnings": warnings,
        "summary": summary,
    }


def import_prediction_folder(
    image_dir: str | Path,
    label_dir: str | Path,
    class_map: dict,
    output_dir: str | Path = PREDICTIONS_DIR,
) -> list[dict[str, Any]]:
    image_root = Path(image_dir)
    image_paths = [
        image_path
        for image_path in sorted(image_root.iterdir(), key=lambda path: path.name.lower())
        if image_path.is_file() and image_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]
    return import_prediction_folder_for_images(image_paths, label_dir, class_map, output_dir)


def import_prediction_folder_for_images(
    image_paths: list[str | Path],
    label_dir: str | Path,
    class_map: dict,
    output_dir: str | Path = PREDICTIONS_DIR,
) -> list[dict[str, Any]]:
    label_root = Path(label_dir)
    image_path_objects = [Path(image_path) for image_path in image_paths]
    image_stems = {image_path.stem for image_path in image_path_objects}
    label_paths = {
        label_path.stem: label_path
        for label_path in label_root.iterdir()
        if label_path.is_file() and label_path.suffix.lower() == ".txt"
    }
    unmatched_label_count = sum(1 for label_stem in label_paths if label_stem not in image_stems)

    results: list[dict[str, Any]] = []
    for image_path in image_path_objects:
        label_path = label_paths.get(image_path.stem, label_root / f"{image_path.stem}.txt")
        result = import_prediction_txt(image_path, label_path, class_map, output_dir)
        results.append(result)

    if results:
        results[0].setdefault("summary", {})["unmatched_label_files"] = unmatched_label_count
    return results


def summarize_import_results(results: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "images_processed": 0,
        "prediction_files_found": 0,
        "imported_predictions": 0,
        "empty_label_files": 0,
        "missing_label_files": 0,
        "unmatched_label_files": 0,
        "invalid_lines_skipped": 0,
    }
    for result in results:
        result_summary = result.get("summary", {})
        if not isinstance(result_summary, dict):
            continue
        for key in summary:
            try:
                summary[key] += int(result_summary.get(key, 0))
            except (TypeError, ValueError):
                continue
    return summary


def _read_image_size(image_path: Path) -> QSize:
    reader = QImageReader(str(image_path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        return size

    image = reader.read()
    if not image.isNull():
        return image.size()

    raise ValueError(f"Could not read image size for {image_path}")


def _label_for_class_id(class_id: str, class_map: dict) -> str:
    normalized_class_id = _normalize_class_id(class_id)
    return str(
        class_map.get(
            normalized_class_id,
            class_map.get(int(normalized_class_id), "unknown"),
        )
        if normalized_class_id.isdigit()
        else "unknown"
    )


def _normalize_class_id(class_id: str) -> str:
    return str(class_id).strip().lstrip("\ufeff")
