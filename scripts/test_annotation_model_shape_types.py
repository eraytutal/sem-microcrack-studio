from __future__ import annotations

import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import annotation_io  # noqa: E402
from src.annotation_model import (  # noqa: E402
    is_polygon_annotation,
    is_rectangle_annotation,
    normalize_annotation,
)


@contextmanager
def temporary_annotations_dir() -> Iterator[Path]:
    original_annotations_dir = annotation_io.ANNOTATIONS_DIR
    with tempfile.TemporaryDirectory() as temp_dir:
        annotations_dir = Path(temp_dir) / "annotations"
        annotation_io.ANNOTATIONS_DIR = annotations_dir
        try:
            yield annotations_dir
        finally:
            annotation_io.ANNOTATIONS_DIR = original_annotations_dir


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def image_path(name: str) -> str:
    return str(Path(tempfile.gettempdir()) / "sem_microcrack_shape_test_images" / name)


def test_rectangle_normalize_load_save() -> None:
    rectangle = {
        "shape_type": "rectangle",
        "x": 10,
        "y": 12,
        "width": 30,
        "height": 24,
        "label": "scratch",
        "source": "manual",
        "confidence": "0.75",
        "exportable_to_mask": False,
        "status": "verified",
        "notes": "rectangle note",
    }

    normalized = normalize_annotation(rectangle, fallback_id="ann_001")
    check(is_rectangle_annotation(normalized), "rectangle should normalize as rectangle")
    check_equal(normalized["shape_type"], "rectangle", "rectangle shape_type")
    check_equal(normalized["bbox"], [10.0, 12.0, 30.0, 24.0], "rectangle bbox")
    check_equal(normalized["label"], "scratch", "rectangle label")
    check_equal(normalized["source"], "manual", "rectangle source")
    check_equal(normalized["confidence"], 0.75, "rectangle confidence")
    check_equal(normalized["exportable_to_mask"], False, "rectangle exportable_to_mask")
    check_equal(normalized["status"], "verified", "rectangle status")
    check_equal(normalized["notes"], "rectangle note", "rectangle notes")

    with temporary_annotations_dir():
        target_image = image_path("rectangle_sample.png")
        annotation_io.save_annotation_json(
            target_image,
            (120, 90),
            [rectangle],
            {"notes": "save context"},
            "annotated",
        )
        loaded = annotation_io.load_annotation_json(target_image)

    check(isinstance(loaded, dict), "saved rectangle JSON should load")
    saved_annotation = loaded["annotations"][0]
    check_equal(saved_annotation["shape_type"], "rectangle", "saved rectangle shape_type")
    check_equal(saved_annotation["bbox"], [10.0, 12.0, 30.0, 24.0], "saved rectangle bbox")
    check_equal(saved_annotation["label"], "scratch", "saved rectangle label")
    check_equal(saved_annotation["source"], "manual", "saved rectangle source")
    check_equal(saved_annotation["confidence"], 0.75, "saved rectangle confidence")
    check_equal(saved_annotation["exportable_to_mask"], False, "saved rectangle exportable_to_mask")
    check_equal(saved_annotation["status"], "verified", "saved rectangle status")
    check_equal(saved_annotation["notes"], "rectangle note", "saved rectangle notes")


def test_polygon_normalize_load_save() -> None:
    polygon = {
        "id": "poly_001",
        "shape_type": "polygon",
        "points": [[1, 2], [15.5, 3], [12, 18], [2, 16]],
        "bbox": [1, 2, 14.5, 16],
        "label": "uncertain",
        "source": "assisted",
        "confidence": 0.91,
        "exportable_to_mask": True,
        "status": "verified",
        "notes": "polygon note",
    }

    normalized = normalize_annotation(polygon, fallback_id="ann_001")
    check(is_polygon_annotation(normalized), "polygon should normalize as polygon")
    check_equal(normalized["shape_type"], "polygon", "polygon shape_type")
    check_equal(normalized["points"], [[1.0, 2.0], [15.5, 3.0], [12.0, 18.0], [2.0, 16.0]], "polygon points")
    check_equal(normalized["bbox"], [1.0, 2.0, 14.5, 16.0], "polygon bbox")
    check_equal(normalized["label"], "uncertain", "polygon label")
    check_equal(normalized["source"], "assisted", "polygon source")
    check_equal(normalized["confidence"], 0.91, "polygon confidence")
    check_equal(normalized["exportable_to_mask"], True, "polygon exportable_to_mask")
    check_equal(normalized["status"], "verified", "polygon status")
    check_equal(normalized["notes"], "polygon note", "polygon notes")

    with temporary_annotations_dir():
        target_image = image_path("polygon_sample.png")
        annotation_io.save_annotation_json(
            target_image,
            (120, 90),
            [polygon],
            {"notes": "save context"},
            "annotated",
        )
        loaded = annotation_io.load_annotation_json(target_image)

    check(isinstance(loaded, dict), "saved polygon JSON should load")
    saved_annotation = loaded["annotations"][0]
    for key in (
        "shape_type",
        "points",
        "bbox",
        "label",
        "source",
        "confidence",
        "exportable_to_mask",
        "status",
        "notes",
    ):
        check_equal(saved_annotation[key], normalized[key], f"saved polygon {key}")


def test_old_rectangle_json_without_shape_fields() -> None:
    with temporary_annotations_dir():
        target_image = image_path("legacy_rectangle.png")
        annotation_path = annotation_io.get_annotation_path(target_image)
        annotation_path.parent.mkdir(parents=True, exist_ok=True)
        annotation_path.write_text(
            json.dumps(
                {
                    "image": {"filename": "legacy_rectangle.png", "width": 80, "height": 60},
                    "annotations": [
                        {
                            "id": "legacy_001",
                            "label": "crack",
                            "bbox": [4, 5, 20, 10],
                            "source": "manual",
                            "confidence": None,
                            "exportable_to_mask": True,
                            "status": "verified",
                            "notes": "legacy note",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        loaded = annotation_io.load_annotation_json(target_image)
        status_data = annotation_io.get_dataset_status([target_image])

    check(isinstance(loaded, dict), "legacy rectangle JSON should load")
    normalized = normalize_annotation(loaded["annotations"][0], fallback_id="ann_001")
    check(is_rectangle_annotation(normalized), "legacy rectangle should normalize as rectangle")
    check_equal(normalized["shape_type"], "rectangle", "legacy rectangle shape_type")
    check_equal(normalized["bbox"], [4.0, 5.0, 20.0, 10.0], "legacy rectangle bbox")
    check_equal(status_data["annotated_images"], 1, "legacy rectangle dataset annotated count")
    check_equal(status_data["rows"][0]["annotation_count"], 1, "legacy rectangle annotation count")


def test_invalid_json_dataset_status_does_not_crash() -> None:
    with temporary_annotations_dir():
        target_image = image_path("invalid_json.png")
        annotation_path = annotation_io.get_annotation_path(target_image)
        annotation_path.parent.mkdir(parents=True, exist_ok=True)
        annotation_path.write_text("{ invalid", encoding="utf-8")
        loaded = annotation_io.load_annotation_json(target_image)
        status_data = annotation_io.get_dataset_status([target_image])

    check_equal(loaded, None, "invalid JSON should load as None")
    check_equal(status_data["unreviewed_images"], 1, "invalid JSON unreviewed count")
    check_equal(status_data["rows"][0]["status"], "Unreviewed", "invalid JSON row status")
    check_equal(status_data["rows"][0]["annotation_count"], 0, "invalid JSON annotation count")


def run_test(name: str, test_func: Callable[[], None]) -> bool:
    try:
        test_func()
    except Exception as error:
        print(f"FAIL {name}: {error}")
        return False

    print(f"PASS {name}")
    return True


def main() -> int:
    tests = [
        ("rectangle normalize/load/save", test_rectangle_normalize_load_save),
        ("polygon normalize/load/save", test_polygon_normalize_load_save),
        ("old rectangle JSON compatibility", test_old_rectangle_json_without_shape_fields),
        ("invalid JSON dataset status", test_invalid_json_dataset_status_does_not_crash),
    ]
    passed = [run_test(name, test_func) for name, test_func in tests]
    if all(passed):
        print("OVERALL PASS")
        return 0

    print("OVERALL FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
