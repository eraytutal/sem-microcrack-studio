from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ANNOTATIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "annotations"


def get_annotation_path(image_path: str) -> Path:
    return ANNOTATIONS_DIR / f"{Path(image_path).stem}.json"


def load_annotation_json(image_path: str) -> dict[str, Any] | None:
    annotation_path = get_annotation_path(image_path)
    if not annotation_path.exists():
        return None

    with annotation_path.open("r", encoding="utf-8") as file:
        return json.load(file)


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
        "annotations": [
            _annotation_payload(index, rect)
            for index, rect in enumerate(annotations, start=1)
        ],
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


def _annotation_payload(
    index: int,
    rect: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"ann_{index:03d}",
        "label": str(rect.get("label") or "crack"),
        "shape_type": "rectangle",
        "bbox": [
            float(rect.get("x", 0.0)),
            float(rect.get("y", 0.0)),
            float(rect.get("width", 0.0)),
            float(rect.get("height", 0.0)),
        ],
        "source": str(rect.get("source") or "manual"),
        "confidence": rect.get("confidence"),
        "exportable_to_mask": bool(rect.get("exportable_to_mask", True)),
        "status": str(rect.get("status") or "verified"),
        "notes": str(rect.get("notes") or ""),
    }
