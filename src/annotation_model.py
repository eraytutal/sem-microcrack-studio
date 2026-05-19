from __future__ import annotations

from typing import Any


COMMON_DEFAULTS = {
    "label": "crack",
    "source": "manual",
    "confidence": None,
    "exportable_to_mask": True,
    "status": "verified",
    "notes": "",
}


def calculate_bbox_from_points(points: list[list[float]]) -> list[float]:
    if not points:
        return [0.0, 0.0, 0.0, 0.0]

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left = min(xs)
    top = min(ys)
    return [left, top, max(xs) - left, max(ys) - top]


def is_rectangle_annotation(annotation: dict[str, Any]) -> bool:
    return normalize_shape_type(annotation) == "rectangle"


def is_polygon_annotation(annotation: dict[str, Any]) -> bool:
    return normalize_shape_type(annotation) == "polygon"


def normalize_annotation(annotation: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    normalized = {
        "id": str(annotation.get("id") or fallback_id or ""),
        **COMMON_DEFAULTS,
    }
    normalized.update(
        {
            "label": str(annotation.get("label") or COMMON_DEFAULTS["label"]),
            "shape_type": normalize_shape_type(annotation),
            "source": str(annotation.get("source") or COMMON_DEFAULTS["source"]),
            "confidence": _normalize_confidence(annotation.get("confidence")),
            "exportable_to_mask": bool(annotation.get("exportable_to_mask", True)),
            "status": str(annotation.get("status") or COMMON_DEFAULTS["status"]),
            "notes": str(annotation.get("notes") or ""),
        }
    )
    if annotation.get("prediction_id"):
        normalized["prediction_id"] = str(annotation.get("prediction_id"))

    if normalized["shape_type"] == "polygon":
        points = _normalize_points(annotation.get("points", []))
        normalized["points"] = points
        normalized["bbox"] = _normalize_bbox(annotation.get("bbox")) or calculate_bbox_from_points(points)
    else:
        normalized["shape_type"] = "rectangle"
        normalized["bbox"] = _normalize_bbox(annotation.get("bbox")) or _bbox_from_xywh(annotation)

    return normalized


def normalize_shape_type(annotation: dict[str, Any]) -> str:
    shape_type = str(annotation.get("shape_type") or "").lower()
    if shape_type == "polygon" or annotation.get("points"):
        return "polygon"
    return "rectangle"


def _normalize_bbox(raw_bbox: Any) -> list[float] | None:
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return None

    try:
        return [float(value) for value in raw_bbox]
    except (TypeError, ValueError):
        return None


def _bbox_from_xywh(annotation: dict[str, Any]) -> list[float]:
    return [
        _float_value(annotation.get("x")),
        _float_value(annotation.get("y")),
        _float_value(annotation.get("width")),
        _float_value(annotation.get("height")),
    ]


def _normalize_points(raw_points: Any) -> list[list[float]]:
    if not isinstance(raw_points, list):
        return []

    points: list[list[float]] = []
    for point in raw_points:
        if not isinstance(point, list) or len(point) < 2:
            continue
        points.append([_float_value(point[0]), _float_value(point[1])])
    return points


def _normalize_confidence(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
