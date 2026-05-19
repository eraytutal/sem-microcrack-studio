from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.annotation_model import calculate_bbox_from_points, normalize_annotation


PREDICTIONS_DIR = Path(__file__).resolve().parent.parent / "data" / "predictions"


def prediction_path_for_image(image_path: str) -> Path:
    return PREDICTIONS_DIR / f"{Path(image_path).stem}.json"


def load_predictions(image_path: str) -> list[dict[str, Any]]:
    prediction_path = prediction_path_for_image(image_path)
    if not prediction_path.exists():
        return []

    try:
        with prediction_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    raw_predictions = data.get("predictions", [])
    if not isinstance(raw_predictions, list):
        return []

    predictions: list[dict[str, Any]] = []
    for index, raw_prediction in enumerate(raw_predictions, start=1):
        if not isinstance(raw_prediction, dict):
            continue

        prediction = _normalize_prediction(raw_prediction, fallback_id=f"pred_{index:03d}")
        if _has_valid_polygon(prediction):
            predictions.append(prediction)
    return predictions


def save_predictions(
    image_path: str,
    image_size: tuple[int, int],
    predictions: list[dict[str, Any]],
) -> Path:
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    image = Path(image_path)
    width, height = image_size
    normalized_predictions: list[dict[str, Any]] = []
    for index, prediction in enumerate(predictions, start=1):
        normalized = _normalize_prediction(prediction, fallback_id=f"pred_{index:03d}")
        if _has_valid_polygon(normalized):
            normalized_predictions.append(normalized)

    payload = {
        "image": {
            "filename": image.name,
            "path": str(image.resolve()).replace("\\", "/"),
            "width": width,
            "height": height,
        },
        "predictions": [_prediction_payload(prediction) for prediction in normalized_predictions],
    }

    prediction_path = prediction_path_for_image(image_path)
    with prediction_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")
    return prediction_path


def generate_dummy_polygon_predictions(
    image_path: str,
    image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    width, height = image_size
    specs = [
        ("crack", 0.82, 0.16, 0.16, 0.30, 0.24),
        ("scratch", 0.61, 0.52, 0.28, 0.24, 0.20),
        ("uncertain", 0.44, 0.30, 0.58, 0.22, 0.18),
    ]
    predictions: list[dict[str, Any]] = []
    for index, (label, confidence, x_ratio, y_ratio, w_ratio, h_ratio) in enumerate(specs, start=1):
        left = max(0.0, min(width - 4.0, width * x_ratio))
        top = max(0.0, min(height - 4.0, height * y_ratio))
        box_width = max(4.0, min(width - left, width * w_ratio))
        box_height = max(4.0, min(height - top, height * h_ratio))
        points = [
            [left, top + box_height * 0.10],
            [left + box_width * 0.78, top],
            [left + box_width, top + box_height * 0.68],
            [left + box_width * 0.24, top + box_height],
        ]
        predictions.append(
            {
                "id": f"pred_{index:03d}",
                "label": label,
                "shape_type": "polygon",
                "points": points,
                "bbox": calculate_bbox_from_points(points),
                "source": "dummy_model",
                "confidence": confidence,
                "status": "pending",
            }
        )
    return predictions


def prediction_to_annotation(prediction: dict[str, Any], annotation_id: str) -> dict[str, Any]:
    normalized = _normalize_prediction(prediction, fallback_id=annotation_id)
    return {
        "id": annotation_id,
        "label": str(normalized.get("label") or "crack"),
        "shape_type": "polygon",
        "points": normalized.get("points", []),
        "bbox": normalized.get("bbox", []),
        "source": "model",
        "confidence": normalized.get("confidence"),
        "exportable_to_mask": True,
        "status": "verified",
        "notes": "",
    }


def _normalize_prediction(prediction: dict[str, Any], fallback_id: str) -> dict[str, Any]:
    normalized = normalize_annotation(
        {
            **prediction,
            "shape_type": "polygon",
            "source": prediction.get("source") or "dummy_model",
            "status": prediction.get("status") or "pending",
        },
        fallback_id=fallback_id,
    )
    normalized["id"] = str(prediction.get("id") or fallback_id)
    normalized["status"] = str(prediction.get("status") or "pending")
    if normalized.get("bbox") == [0.0, 0.0, 0.0, 0.0]:
        normalized["bbox"] = calculate_bbox_from_points(normalized.get("points", []))
    return normalized


def _has_valid_polygon(prediction: dict[str, Any]) -> bool:
    points = prediction.get("points", [])
    return isinstance(points, list) and len(points) >= 3


def _prediction_payload(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(prediction.get("id") or ""),
        "label": str(prediction.get("label") or "crack"),
        "shape_type": "polygon",
        "points": prediction.get("points", []),
        "bbox": prediction.get("bbox") or calculate_bbox_from_points(prediction.get("points", [])),
        "source": str(prediction.get("source") or "dummy_model"),
        "confidence": prediction.get("confidence"),
        "status": str(prediction.get("status") or "pending"),
    }
