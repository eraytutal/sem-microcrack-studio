from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QColor, QImage


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.yolo_seg_export import (  # noqa: E402
    DEFAULT_CLASS_MAP,
    annotation_to_yolo_seg_line,
    export_yolo_seg_dataset,
    rectangle_bbox_to_polygon_points,
    split_images,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def make_image(path: Path, width: int = 1000, height: int = 500) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor("#111111"))
    if not image.save(str(path)):
        raise RuntimeError(f"Could not create image: {path}")


def write_annotation_json(
    annotations_dir: Path,
    image_path: Path,
    annotations: list[dict],
    image_status: str = "annotated",
    width: int = 1000,
    height: int = 500,
) -> Path:
    annotations_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "image": {
            "filename": image_path.name,
            "path": str(image_path.resolve()).replace("\\", "/"),
            "width": width,
            "height": height,
        },
        "image_status": image_status,
        "metadata": {},
        "annotations": annotations,
    }
    annotation_path = annotations_dir / f"{image_path.stem}.json"
    annotation_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return annotation_path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_label(output_dir: Path, stem: str) -> Path:
    matches = list((output_dir / "labels").rglob(f"{stem}.txt"))
    check_equal(len(matches), 1, f"label file count for {stem}")
    return matches[0]


def test_1_rectangle_to_yolo_seg_polygon() -> None:
    points = rectangle_bbox_to_polygon_points([100, 100, 200, 100])
    check_equal(points, [[100.0, 100.0], [300.0, 100.0], [300.0, 200.0], [100.0, 200.0]], "rect points")
    line, counters = annotation_to_yolo_seg_line(
        {
            "label": "crack",
            "shape_type": "rectangle",
            "bbox": [100, 100, 200, 100],
            "status": "verified",
            "exportable_to_mask": True,
        },
        1000,
        500,
        DEFAULT_CLASS_MAP,
    )
    check_equal(line, "0 0.1 0.2 0.3 0.2 0.3 0.4 0.1 0.4", "rectangle YOLO line")
    check_equal(len(str(line).split()), 9, "rectangle YOLO line token count")
    check_equal(counters["rectangles_converted_to_polygons"], 1, "rectangle conversion count")


def test_2_polygon_export_line() -> None:
    line, counters = annotation_to_yolo_seg_line(
        {
            "label": "crack",
            "shape_type": "polygon",
            "points": [[100, 100], [300, 100], [300, 200], [100, 200]],
            "status": "verified",
            "exportable_to_mask": True,
        },
        1000,
        500,
        DEFAULT_CLASS_MAP,
    )
    check_equal(line, "0 0.1 0.2 0.3 0.2 0.3 0.4 0.1 0.4", "polygon YOLO line")
    check_equal(len(str(line).split()), 9, "polygon YOLO line token count")
    check_equal(counters["polygons_exported"], 1, "polygon export count")

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "polygon_source.png"
        make_image(image_path)
        annotation_path = write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "label": "crack",
                    "shape_type": "polygon",
                    "points": [[100, 100], [300, 100], [300, 200], [100, 200]],
                    "status": "verified",
                    "exportable_to_mask": True,
                }
            ],
        )
        before = read_json(annotation_path)
        export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)
        after = read_json(annotation_path)

    check_equal(after["annotations"][0]["shape_type"], "polygon", "source polygon shape_type unchanged")
    check_equal(after, before, "source polygon JSON unchanged")


def test_3_mixed_rectangle_polygon_export() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "mixed.png"
        make_image(image_path)
        annotation_path = write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "id": "ann_001",
                    "label": "crack",
                    "shape_type": "rectangle",
                    "bbox": [100, 100, 200, 100],
                    "status": "verified",
                    "exportable_to_mask": True,
                },
                {
                    "id": "ann_002",
                    "label": "scratch",
                    "shape_type": "polygon",
                    "points": [[100, 100], [300, 100], [300, 200], [100, 200]],
                    "status": "verified",
                    "exportable_to_mask": True,
                },
            ],
        )
        before = annotation_path.read_bytes()

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir, seed=42)
        label_text = find_label(output_dir, "mixed").read_text(encoding="utf-8").strip().splitlines()
        after = annotation_path.read_bytes()

    check_equal(label_text[0], "0 0.1 0.2 0.3 0.2 0.3 0.4 0.1 0.4", "mixed rectangle line")
    check_equal(label_text[1], "1 0.1 0.2 0.3 0.2 0.3 0.4 0.1 0.4", "mixed polygon line")
    check_equal(report["labels_written"], 2, "mixed labels written")
    check_equal(report["rectangles_converted_to_polygons"], 1, "mixed rectangle count")
    check_equal(report["polygons_exported"], 1, "mixed polygon count")
    check_equal(before, after, "source annotation JSON unchanged")


def test_4_no_defect_export_empty_label() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "negative.png"
        make_image(image_path)
        write_annotation_json(annotations_dir, image_path, [], image_status="reviewed_no_defect")

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)
        label_path = find_label(output_dir, "negative")
        label_text = label_path.read_text(encoding="utf-8")

    check_equal(label_text, "", "no-defect empty label")
    check_equal(report["no_defect_images_exported"], 1, "no-defect count")
    check_equal(report["empty_label_files_written"], 1, "empty label count")


def test_5_unreviewed_image_skipped_and_predictions_ignored() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        predictions_dir = root / "predictions"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "unreviewed.png"
        make_image(image_path)
        predictions_dir.mkdir(parents=True)
        (predictions_dir / "unreviewed.json").write_text(
            json.dumps({"predictions": [{"label": "crack"}]}),
            encoding="utf-8",
        )

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)

    check_equal(report["images_exported"], 0, "unreviewed exported count")
    check_equal(report["skipped_unreviewed"], 1, "unreviewed skipped count")
    check_equal(list((output_dir / "labels").rglob("*.txt")), [], "prediction JSON should not create labels")


def test_6_uncertain_excluded_by_default() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "uncertain.png"
        make_image(image_path)
        write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "label": "uncertain",
                    "shape_type": "rectangle",
                    "bbox": [100, 100, 200, 100],
                    "status": "verified",
                    "exportable_to_mask": True,
                }
            ],
        )

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)

    check_equal(report["images_exported"], 0, "uncertain image exported count")
    check_equal(report["skipped_uncertain"], 1, "uncertain skipped count")


def test_7_exportable_false_skipped() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "not_exportable.png"
        make_image(image_path)
        write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "label": "crack",
                    "shape_type": "rectangle",
                    "bbox": [100, 100, 200, 100],
                    "status": "verified",
                    "exportable_to_mask": False,
                }
            ],
        )

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)

    check_equal(report["images_exported"], 0, "not exportable image exported count")
    check_equal(report["skipped_not_exportable"], 1, "not exportable skipped count")


def test_8_invalid_geometry_skipped() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        bad_rect = image_dir / "bad_rect.png"
        bad_polygon = image_dir / "bad_polygon.png"
        make_image(bad_rect)
        make_image(bad_polygon)
        write_annotation_json(
            annotations_dir,
            bad_rect,
            [
                {
                    "label": "crack",
                    "shape_type": "rectangle",
                    "status": "verified",
                    "exportable_to_mask": True,
                }
            ],
        )
        write_annotation_json(
            annotations_dir,
            bad_polygon,
            [
                {
                    "label": "crack",
                    "shape_type": "polygon",
                    "points": [[100, 100], [200, 200]],
                    "status": "verified",
                    "exportable_to_mask": True,
                }
            ],
        )

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)

    check_equal(report["images_exported"], 0, "invalid geometry exported count")
    check_equal(report["skipped_invalid_geometry"], 2, "invalid geometry skipped count")


def test_9_split_deterministic() -> None:
    records = [{"image_path": Path(f"{index}.png"), "label_lines": [], "class_counts": {}} for index in range(10)]
    first = split_images(records, seed=42)
    second = split_images(records, seed=42)
    check_equal(
        {split: [str(record["image_path"]) for record in items] for split, items in first.items()},
        {split: [str(record["image_path"]) for record in items] for split, items in second.items()},
        "deterministic split",
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_a = root / "exports_a" / "yolo_seg"
        output_b = root / "exports_b" / "yolo_seg"
        for index in range(10):
            image_path = image_dir / f"image_{index:02d}.png"
            make_image(image_path)
            write_annotation_json(
                annotations_dir,
                image_path,
                [
                    {
                        "label": "crack",
                        "shape_type": "rectangle",
                        "bbox": [100, 100, 200, 100],
                        "status": "verified",
                        "exportable_to_mask": True,
                    }
                ],
            )

        export_yolo_seg_dataset(image_dir, output_a, annotations_dir, seed=42)
        export_yolo_seg_dataset(image_dir, output_b, annotations_dir, seed=42)

        def split_listing(output_dir: Path) -> dict[str, list[str]]:
            return {
                split: sorted(path.name for path in (output_dir / "images" / split).glob("*.png"))
                for split in ("train", "val", "test")
            }

        listing_a = split_listing(output_a)
        listing_b = split_listing(output_b)
        split_dirs = {
            split: {
                "images_exists": (output_a / "images" / split).exists(),
                "labels_exists": (output_a / "labels" / split).exists(),
                "images": sorted(path.name for path in (output_a / "images" / split).glob("*.png")),
                "labels": sorted(path.name for path in (output_a / "labels" / split).glob("*.txt")),
            }
            for split in ("train", "val", "test")
        }

    check_equal(listing_a, listing_b, "export split should be deterministic")
    for split in ("train", "val", "test"):
        check(split_dirs[split]["images_exists"], f"images/{split} exists")
        check(split_dirs[split]["labels_exists"], f"labels/{split} exists")
        check(split_dirs[split]["images"], f"images/{split} has files")
        check(split_dirs[split]["labels"], f"labels/{split} has files")


def test_10_data_yaml_and_report_written() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "yaml.png"
        make_image(image_path)
        write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "label": "crack",
                    "shape_type": "rectangle",
                    "bbox": [100, 100, 200, 100],
                    "status": "verified",
                    "exportable_to_mask": True,
                }
            ],
        )

        export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)
        data_yaml = (output_dir / "data.yaml").read_text(encoding="utf-8")
        report = read_json(output_dir / "export_report.json")

    check("train: images/train" in data_yaml, "data.yaml train path")
    check("val: images/val" in data_yaml, "data.yaml val path")
    check("test: images/test" in data_yaml, "data.yaml test path")
    check("0: crack" in data_yaml, "data.yaml crack name")
    check("1: scratch" in data_yaml, "data.yaml scratch name")
    check("2: pit" in data_yaml, "data.yaml pit name")
    check("3: void" in data_yaml, "data.yaml void name")
    check("uncertain" not in data_yaml, "data.yaml excludes uncertain by default")
    for key in [
        "total_images_seen",
        "images_exported",
        "annotation_files_read",
        "labels_written",
        "empty_label_files_written",
        "rectangles_converted_to_polygons",
        "polygons_exported",
        "no_defect_images_exported",
        "skipped_unreviewed",
        "skipped_uncertain",
        "skipped_invalid_geometry",
        "skipped_not_exportable",
        "split",
    ]:
        check(key in report, f"report contains {key}")
    for split in ("train", "val", "test"):
        check(split in report["split"], f"report split contains {split}")


def test_11_source_json_unchanged() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "unchanged.png"
        make_image(image_path)
        annotation_path = write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "id": "ann_manual",
                    "label": "crack",
                    "shape_type": "rectangle",
                    "bbox": [100, 100, 200, 100],
                    "status": "verified",
                    "exportable_to_mask": True,
                    "notes": "source should remain byte-identical",
                }
            ],
        )
        before = annotation_path.read_bytes()
        export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)
        after = annotation_path.read_bytes()

    check_equal(after, before, "source annotation JSON byte-for-byte unchanged")


def test_12_predictions_not_used_directly() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        predictions_dir = root / "predictions"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "prediction_only.png"
        make_image(image_path)
        predictions_dir.mkdir(parents=True)
        (predictions_dir / "prediction_only.json").write_text(
            json.dumps(
                {
                    "image": {"filename": image_path.name},
                    "predictions": [
                        {
                            "id": "pred_001",
                            "label": "crack",
                            "shape_type": "polygon",
                            "points": [[100, 100], [300, 100], [300, 200], [100, 200]],
                            "status": "accepted",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)

    check_equal(report["images_exported"], 0, "prediction-only JSON should not be exported")
    check_equal(report["skipped_unreviewed"], 1, "prediction-only image should remain unreviewed")


def test_13_accepted_model_annotation_exports_from_annotations() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        annotations_dir = root / "annotations"
        predictions_dir = root / "predictions"
        output_dir = root / "exports" / "yolo_seg"
        image_path = image_dir / "accepted_model.png"
        make_image(image_path)
        predictions_dir.mkdir(parents=True)
        (predictions_dir / "accepted_model.json").write_text(
            json.dumps({"predictions": [{"id": "pred_ignored", "label": "scratch"}]}, indent=2) + "\n",
            encoding="utf-8",
        )
        write_annotation_json(
            annotations_dir,
            image_path,
            [
                {
                    "id": "ann_from_accepted_model_pred_001",
                    "prediction_id": "pred_001",
                    "label": "crack",
                    "shape_type": "polygon",
                    "points": [[100, 100], [300, 100], [300, 200], [100, 200]],
                    "source": "model",
                    "confidence": 0.87,
                    "status": "verified",
                    "exportable_to_mask": True,
                }
            ],
        )

        report = export_yolo_seg_dataset(image_dir, output_dir, annotations_dir)
        label_text = find_label(output_dir, "accepted_model").read_text(encoding="utf-8").strip()

    check_equal(report["images_exported"], 1, "accepted model annotation should export")
    check_equal(label_text, "0 0.1 0.2 0.3 0.2 0.3 0.4 0.1 0.4", "accepted model annotation YOLO line")


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
        ("1 rectangle to YOLO-seg polygon", test_1_rectangle_to_yolo_seg_polygon),
        ("2 polygon export", test_2_polygon_export_line),
        ("3 mixed rectangle polygon export", test_3_mixed_rectangle_polygon_export),
        ("4 no defect export", test_4_no_defect_export_empty_label),
        ("5 unreviewed skipped and predictions ignored", test_5_unreviewed_image_skipped_and_predictions_ignored),
        ("6 uncertain excluded by default", test_6_uncertain_excluded_by_default),
        ("7 exportable false skipped", test_7_exportable_false_skipped),
        ("8 invalid geometry skipped", test_8_invalid_geometry_skipped),
        ("9 split deterministic", test_9_split_deterministic),
        ("10 data yaml and report", test_10_data_yaml_and_report_written),
        ("11 source JSON unchanged", test_11_source_json_unchanged),
        ("12 predictions not used directly", test_12_predictions_not_used_directly),
        ("13 accepted model annotation exports", test_13_accepted_model_annotation_exports_from_annotations),
    ]
    passed = [run_test(name, test_func) for name, test_func in tests]
    if all(passed):
        print("OVERALL PASS")
        return 0

    print("OVERALL FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
