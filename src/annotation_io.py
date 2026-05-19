from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.annotation_model import normalize_annotation


ANNOTATIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "annotations"


def get_annotation_path(image_path: str) -> Path:
    return ANNOTATIONS_DIR / f"{Path(image_path).stem}.json"


def load_annotation_json(image_path: str) -> dict[str, Any] | None:
    annotation_path = get_annotation_path(image_path)
    if not annotation_path.exists():
        return None

    try:
        with annotation_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def get_image_annotation_status(image_path: str) -> dict[str, Any]:
    data = load_annotation_json(image_path)
    if not data:
        return {
            "image_path": image_path,
            "filename": Path(image_path).name,
            "status": "Unreviewed",
            "annotation_count": 0,
        }

    raw_annotations = data.get("annotations", [])
    annotations = _normalized_annotations(raw_annotations)
    annotation_count = len(annotations)
    image_status = data.get("image_status")

    if image_status == "annotated":
        status = "Annotated"
    elif image_status == "reviewed_no_defect":
        status = "No Defect"
    elif image_status == "unreviewed":
        status = "Unreviewed"
    else:
        status = "Annotated" if annotation_count > 0 else "Unreviewed"

    return {
        "image_path": image_path,
        "filename": Path(image_path).name,
        "status": status,
        "annotation_count": annotation_count,
    }


def get_dataset_status(image_paths: list[str]) -> dict[str, Any]:
    rows = [get_image_annotation_status(image_path) for image_path in image_paths]
    annotated = sum(1 for row in rows if row["status"] == "Annotated")
    no_defect = sum(1 for row in rows if row["status"] == "No Defect")
    unreviewed = sum(1 for row in rows if row["status"] == "Unreviewed")

    return {
        "total_images": len(rows),
        "annotated_images": annotated,
        "no_defect_images": no_defect,
        "unreviewed_images": unreviewed,
        "rows": rows,
    }


def save_annotation_json(
    image_path: str,
    image_size: tuple[int, int],
    annotations: list[dict[str, Any]],
    metadata: dict[str, Any],
    image_status: str = "unreviewed",
) -> Path:
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)

    image = Path(image_path)
    width, height = image_size

    payload = {
        "image": {
            "filename": image.name,
            "path": str(image.resolve()).replace("\\", "/"),
            "width": width,
            "height": height,
        },
        "image_status": _normalize_image_status(image_status, annotations),
        "metadata": {
            "material": str(metadata.get("material", "")),
            "magnification": str(metadata.get("magnification", "")),
            "scale_value": metadata.get("scale_value"),
            "scale_unit": str(metadata.get("scale_unit", "um")),
            "scale_bar_px": metadata.get("scale_bar_px"),
            "sem_mode": str(metadata.get("sem_mode", "")),
            "image_quality": str(metadata.get("image_quality", "")),
            "notes": str(metadata.get("notes", "")),
        },
        "annotations": _annotation_payloads(annotations),
    }

    annotation_path = get_annotation_path(image_path)
    with annotation_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")

    return annotation_path


def _normalize_image_status(image_status: str, annotations: list[dict[str, Any]]) -> str:
    if annotations:
        return "annotated"
    if image_status == "reviewed_no_defect":
        return "reviewed_no_defect"
    return "unreviewed"


def _annotation_payloads(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        normalize_annotation(annotation, fallback_id=f"ann_{index:03d}")
        for index, annotation in enumerate(annotations, start=1)
    ]


def _normalized_annotations(raw_annotations: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_annotations, list):
        return []

    return [
        normalize_annotation(annotation, fallback_id=f"ann_{index:03d}")
        for index, annotation in enumerate(raw_annotations, start=1)
        if isinstance(annotation, dict)
    ]
