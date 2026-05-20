from __future__ import annotations

import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from PySide6.QtGui import QColor, QImage


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import annotation_io, prediction_io  # noqa: E402
from src.model_prediction_import import (  # noqa: E402
    DEFAULT_CLASS_MAP,
    import_prediction_folder,
    import_prediction_folder_for_images,
    import_prediction_txt,
    parse_yolo_seg_line,
    summarize_import_results,
)
from src.prediction_io import generate_dummy_polygon_predictions, load_predictions, save_predictions  # noqa: E402


CLASS_MAP = {"0": "crack", "1": "scratch"}


@contextmanager
def real_data_guard() -> Iterator[None]:
    annotations_before = _directory_snapshot(PROJECT_ROOT / "data" / "annotations")
    predictions_before = _directory_snapshot(PROJECT_ROOT / "data" / "predictions")
    try:
        yield
    finally:
        check_equal(
            _directory_snapshot(PROJECT_ROOT / "data" / "annotations"),
            annotations_before,
            "real data/annotations JSON files should not change",
        )
        check_equal(
            _directory_snapshot(PROJECT_ROOT / "data" / "predictions"),
            predictions_before,
            "real data/predictions JSON files should not change",
        )


@contextmanager
def temporary_prediction_dir(root: Path) -> Iterator[Path]:
    original_predictions_dir = prediction_io.PREDICTIONS_DIR
    prediction_io.PREDICTIONS_DIR = root / "predictions"
    try:
        yield prediction_io.PREDICTIONS_DIR
    finally:
        prediction_io.PREDICTIONS_DIR = original_predictions_dir


def _directory_snapshot(directory: Path) -> dict[str, tuple[int, int]]:
    if not directory.exists():
        return {}

    return {
        str(path.relative_to(directory)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(directory.rglob("*.json"))
        if path.is_file()
    }


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
        raise RuntimeError(f"Could not create test image: {path}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_1_normalized_polygon_with_confidence() -> None:
    prediction = parse_yolo_seg_line(
        "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87",
        1000,
        500,
        CLASS_MAP,
    )

    check(isinstance(prediction, dict), "prediction should parse")
    check_equal(prediction["label"], CLASS_MAP["0"], "label")
    check_equal(prediction["shape_type"], "polygon", "shape_type")
    check_equal(prediction["source"], "model_import", "source")
    check_equal(prediction["status"], "pending", "status")
    check_equal(prediction["confidence"], 0.87, "confidence")
    check_equal(
        prediction["points"],
        [[100.0, 100.0], [300.0, 100.0], [300.0, 200.0], [100.0, 200.0]],
        "pixel points",
    )
    check_equal(prediction["bbox"], [100.0, 100.0, 200.0, 100.0], "bbox")


def test_2_normalized_polygon_without_confidence() -> None:
    prediction = parse_yolo_seg_line(
        "1 0.50 0.50 0.60 0.50 0.60 0.60 0.50 0.60",
        1000,
        500,
        CLASS_MAP,
    )

    check(isinstance(prediction, dict), "prediction should parse")
    check_equal(prediction["label"], CLASS_MAP["1"], "label")
    check_equal(prediction["confidence"], None, "confidence")
    check_equal(
        prediction["points"],
        [[500.0, 250.0], [600.0, 250.0], [600.0, 300.0], [500.0, 300.0]],
        "pixel points",
    )
    check_equal(prediction["bbox"], [500.0, 250.0, 100.0, 50.0], "bbox")


def test_3_unknown_class_id() -> None:
    prediction = parse_yolo_seg_line(
        "99 0.10 0.10 0.20 0.10 0.20 0.30",
        1000,
        500,
        CLASS_MAP,
    )

    check(isinstance(prediction, dict), "unknown class polygon should parse")
    check_equal(prediction["label"], "unknown", "unknown label fallback")


def test_4_utf8_bom_class_id() -> None:
    prediction = parse_yolo_seg_line(
        "\ufeff0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87",
        1000,
        500,
        {"0": "crack"},
    )

    check(isinstance(prediction, dict), "BOM-prefixed class id should parse")
    check_equal(prediction["label"], "crack", "BOM-prefixed class id label")
    check(prediction["label"] != "unknown", "BOM-prefixed class id should not map to unknown")
    check_equal(prediction["shape_type"], "polygon", "BOM-prefixed line shape_type")
    check_equal(prediction["confidence"], 0.87, "BOM-prefixed line confidence")
    check_equal(
        prediction["points"],
        [[100.0, 100.0], [300.0, 100.0], [300.0, 200.0], [100.0, 200.0]],
        "BOM-prefixed line points",
    )
    check_equal(prediction["bbox"], [100.0, 100.0, 200.0, 100.0], "BOM-prefixed line bbox")


def test_5_utf8_bom_temp_label_file() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "bom_image.png"
        label_path = root / "bom_image.txt"
        output_dir = root / "predictions"
        annotations_dir = root / "annotations"
        make_image(image_path, 1000, 500)
        label_path.write_bytes(
            "\ufeff0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87".encode("utf-8")
        )

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, {"0": "crack"}, output_dir)

        output_path = Path(result["output_path"])
        payload = read_json(output_path)
        annotations_dir_exists = annotations_dir.exists()

    check_equal(len(payload["predictions"]), 1, "BOM label file prediction count")
    prediction = payload["predictions"][0]
    check_equal(prediction["label"], "crack", "BOM label file prediction label")
    check(prediction["label"] != "unknown", "BOM label file should not map to unknown")
    check_equal(prediction["shape_type"], "polygon", "BOM label file shape_type")
    check_equal(prediction["confidence"], 0.87, "BOM label file confidence")
    check_equal(
        prediction["points"],
        [[100.0, 100.0], [300.0, 100.0], [300.0, 200.0], [100.0, 200.0]],
        "BOM label file points",
    )
    check_equal(prediction["bbox"], [100.0, 100.0, 200.0, 100.0], "BOM label file bbox")
    check_equal(annotations_dir_exists, False, "BOM import should not create annotations dir")


def test_6_invalid_short_polygon() -> None:
    check_equal(
        parse_yolo_seg_line("0 0.10 0.20 0.30 0.20", 1000, 500, CLASS_MAP),
        None,
        "short polygon should be skipped",
    )
    check_equal(
        parse_yolo_seg_line("0 0.10 0.20 bad 0.20 0.30 0.40", 1000, 500, CLASS_MAP),
        None,
        "non-numeric polygon should be skipped",
    )
    check_equal(
        parse_yolo_seg_line("0 1.10 0.20 0.30 0.20 0.30 0.40", 1000, 500, CLASS_MAP),
        None,
        "out-of-range normalized coordinate should be skipped",
    )


def test_7_empty_file_outputs_valid_json() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "empty.png"
        label_path = root / "empty.txt"
        output_dir = root / "predictions"
        make_image(image_path)
        label_path.write_text("", encoding="utf-8")

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, CLASS_MAP, output_dir)

        payload = read_json(output_dir / "empty.json")

    check_equal(result["predictions"], [], "empty file result predictions")
    check_equal(payload["predictions"], [], "empty file JSON predictions")
    check_equal(result["summary"]["empty_label_files"], 1, "empty file summary count")
    check_equal(result["summary"]["imported_predictions"], 0, "empty file imported count")
    check_equal(payload["image"]["filename"], "empty.png", "image filename")
    check_equal(payload["image"]["width"], 1000, "image width")
    check_equal(payload["image"]["height"], 500, "image height")


def test_8_whitespace_only_file_outputs_valid_json() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "whitespace.png"
        label_path = root / "whitespace.txt"
        output_dir = root / "predictions"
        make_image(image_path)
        label_path.write_text("   \n\t\n", encoding="utf-8")

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, CLASS_MAP, output_dir)

        payload = read_json(output_dir / "whitespace.json")

    check_equal(result["predictions"], [], "whitespace file result predictions")
    check_equal(payload["predictions"], [], "whitespace file JSON predictions")
    check_equal(result["summary"]["empty_label_files"], 1, "whitespace file summary count")
    check_equal(result["warnings"], [], "whitespace-only file should not warn")


def test_9_multiple_lines_skip_invalid_and_assign_deterministic_ids() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "multi.png"
        label_path = root / "multi.txt"
        output_dir = root / "predictions"
        make_image(image_path)
        label_path.write_text(
            "\n".join(
                [
                    "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87",
                    "not a valid prediction line",
                    "99 0.50 0.50 0.60 0.50 0.60 0.60 0.50 0.60",
                ]
            ),
            encoding="utf-8",
        )

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, CLASS_MAP, output_dir)

    predictions = result["predictions"]
    check_equal(len(predictions), 2, "only valid prediction count")
    check_equal([item["id"] for item in predictions], ["pred_001", "pred_002"], "deterministic ids")
    check_equal(predictions[0]["label"], "crack", "first label")
    check_equal(predictions[1]["label"], "unknown", "unknown label")
    check(result["warnings"], "invalid line should produce warning")
    check_equal(result["summary"]["invalid_lines_skipped"], 1, "invalid line count")
    check_equal(result["summary"]["imported_predictions"], 2, "mixed import count")


def test_10_bbox_only_yolo_line_is_not_polygon() -> None:
    line = "0 0.5 0.5 0.2 0.1 0.91"
    check_equal(
        parse_yolo_seg_line(line, 1000, 500, CLASS_MAP),
        None,
        "bbox-only YOLO line should not be treated as polygon",
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "bbox.png"
        label_path = root / "bbox.txt"
        output_dir = root / "predictions"
        make_image(image_path)
        label_path.write_text(line, encoding="utf-8")

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, CLASS_MAP, output_dir)

    check_equal(result["predictions"], [], "bbox-only import should produce no predictions")
    check(result["warnings"], "bbox-only import should produce warning")
    check_equal(result["summary"]["invalid_lines_skipped"], 1, "bbox-only skipped count")


def test_11_import_single_txt_writes_predictions_only() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "test_image.png"
        label_path = root / "test_image.txt"
        output_dir = root / "predictions"
        annotations_dir = root / "annotations"
        make_image(image_path)
        label_path.write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87",
            encoding="utf-8",
        )

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, CLASS_MAP, output_dir)

        output_path = Path(result["output_path"])
        payload = read_json(output_path)
        output_exists = output_path.exists()
        output_parent = output_path.parent
        annotations_dir_exists = annotations_dir.exists()

    check(output_exists, "single import should write prediction JSON")
    check_equal(output_parent, output_dir, "single import output dir")
    check_equal(payload["image"]["filename"], "test_image.png", "single import image filename")
    check_equal(len(payload["predictions"]), 1, "single import prediction count")
    check_equal(payload["predictions"][0]["id"], "pred_001", "single import prediction id")
    check_equal(payload["predictions"][0]["shape_type"], "polygon", "single import shape")
    check_equal(result["summary"]["prediction_files_found"], 1, "single import file found")
    check_equal(result["summary"]["imported_predictions"], 1, "single import summary count")
    check_equal(annotations_dir_exists, False, "single import should not create annotations dir")


def test_12_import_folder_handles_missing_labels_and_summarizes() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        label_dir = root / "labels"
        output_dir = root / "predictions"
        make_image(image_dir / "a.png", 1000, 500)
        make_image(image_dir / "b.png", 1000, 500)
        make_image(image_dir / "c.png", 1000, 500)
        label_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / "a.txt").write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40",
            encoding="utf-8",
        )
        (label_dir / "b.txt").write_text(
            "",
            encoding="utf-8",
        )
        (label_dir / "extra.txt").write_text(
            "0 0.10 0.10 0.20 0.10 0.20 0.20",
            encoding="utf-8",
        )

        with real_data_guard():
            results = import_prediction_folder(image_dir, label_dir, CLASS_MAP, output_dir)

        payload_a = read_json(output_dir / "a.json")
        payload_b = read_json(output_dir / "b.json")
        payload_c = read_json(output_dir / "c.json")
        summary = summarize_import_results(results)
        output_a_exists = (output_dir / "a.json").exists()
        output_b_exists = (output_dir / "b.json").exists()
        output_c_exists = (output_dir / "c.json").exists()

    check_equal(len(results), 3, "folder import result count")
    check_equal(output_a_exists, True, "a prediction JSON exists")
    check_equal(output_b_exists, True, "b prediction JSON exists")
    check_equal(output_c_exists, True, "c prediction JSON exists")
    check_equal(payload_a["predictions"][0]["label"], "crack", "a prediction label")
    check_equal(payload_b["predictions"], [], "empty b label predictions")
    check_equal(payload_c["predictions"], [], "missing c label predictions")
    check_equal(summary["images_processed"], 3, "folder summary images")
    check_equal(summary["prediction_files_found"], 2, "folder summary found labels")
    check_equal(summary["imported_predictions"], 1, "folder summary imported predictions")
    check_equal(summary["empty_label_files"], 1, "folder summary empty labels")
    check_equal(summary["missing_label_files"], 1, "folder summary missing labels")
    check_equal(summary["unmatched_label_files"], 1, "folder summary unmatched labels")
    check_equal((output_dir / "extra.json").exists(), False, "unmatched label should not create JSON")


def test_13_folder_for_images_uses_loaded_images_only() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        label_dir = root / "labels"
        output_dir = root / "predictions"
        image_a = image_dir / "a.png"
        image_b = image_dir / "b.png"
        image_c = image_dir / "c.png"
        make_image(image_a, 1000, 500)
        make_image(image_b, 1000, 500)
        make_image(image_c, 1000, 500)
        label_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / "a.txt").write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40",
            encoding="utf-8",
        )
        (label_dir / "c.txt").write_text(
            "1 0.50 0.50 0.60 0.50 0.60 0.60 0.50 0.60",
            encoding="utf-8",
        )

        with real_data_guard():
            results = import_prediction_folder_for_images([image_a, image_b], label_dir, CLASS_MAP, output_dir)

        payload_a = read_json(output_dir / "a.json")
        payload_b = read_json(output_dir / "b.json")
        summary = summarize_import_results(results)

    check_equal(len(results), 2, "loaded-image-only result count")
    check_equal(len(payload_a["predictions"]), 1, "loaded image a predictions")
    check_equal(payload_b["predictions"], [], "loaded image b missing label predictions")
    check_equal((output_dir / "c.json").exists(), False, "unloaded image c should not be imported")
    check_equal(summary["images_processed"], 2, "loaded-image-only images processed")
    check_equal(summary["prediction_files_found"], 1, "loaded-image-only matching labels")
    check_equal(summary["missing_label_files"], 1, "loaded-image-only missing labels")
    check_equal(summary["unmatched_label_files"], 1, "loaded-image-only unmatched label count")


def test_14_unicode_filename_import() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "断裂.png"
        label_path = root / "断裂.txt"
        output_dir = root / "predictions"
        make_image(image_path, 1000, 500)
        label_path.write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87",
            encoding="utf-8",
        )

        with real_data_guard():
            result = import_prediction_txt(image_path, label_path, CLASS_MAP, output_dir)

        payload = read_json(output_dir / "断裂.json")

    check_equal(Path(result["output_path"]).name, "断裂.json", "unicode output filename")
    check_equal(payload["image"]["filename"], "断裂.png", "unicode image filename")
    check_equal(payload["predictions"][0]["label"], "crack", "unicode prediction label")


def test_15_annotation_safety_and_dummy_workflow() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "dummy.png"
        output_dir = root / "predictions"
        annotations_dir = root / "annotations"
        make_image(image_path, 320, 240)

        with temporary_prediction_dir(root), real_data_guard():
            predictions = generate_dummy_polygon_predictions(str(image_path), (320, 240))
            save_predictions(str(image_path), (320, 240), predictions)
            loaded = load_predictions(str(image_path))
            output_dir_exists = output_dir.exists()
            annotations_dir_exists = annotations_dir.exists()

    check_equal(len(loaded), 3, "dummy workflow prediction count")
    check_equal([item["id"] for item in loaded], ["pred_001", "pred_002", "pred_003"], "dummy deterministic ids")
    check_equal({item["source"] for item in loaded}, {"dummy_model"}, "dummy source unaffected")
    check_equal(output_dir_exists, True, "dummy workflow writes temp predictions")
    check_equal(annotations_dir_exists, False, "dummy workflow should not create annotations")


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
        ("1 normalized polygon with confidence", test_1_normalized_polygon_with_confidence),
        ("2 normalized polygon without confidence", test_2_normalized_polygon_without_confidence),
        ("3 unknown class id", test_3_unknown_class_id),
        ("4 UTF-8 BOM class id", test_4_utf8_bom_class_id),
        ("5 UTF-8 BOM temp label file", test_5_utf8_bom_temp_label_file),
        ("6 invalid short polygon", test_6_invalid_short_polygon),
        ("7 empty file output JSON", test_7_empty_file_outputs_valid_json),
        ("8 whitespace-only file output JSON", test_8_whitespace_only_file_outputs_valid_json),
        ("9 multiple lines deterministic ids", test_9_multiple_lines_skip_invalid_and_assign_deterministic_ids),
        ("10 bbox-only YOLO line skipped", test_10_bbox_only_yolo_line_is_not_polygon),
        ("11 import single txt", test_11_import_single_txt_writes_predictions_only),
        ("12 import folder missing labels", test_12_import_folder_handles_missing_labels_and_summarizes),
        ("13 folder import uses loaded images only", test_13_folder_for_images_uses_loaded_images_only),
        ("14 unicode filename import", test_14_unicode_filename_import),
        ("15 annotation safety and dummy workflow", test_15_annotation_safety_and_dummy_workflow),
    ]
    passed = [run_test(name, test_func) for name, test_func in tests]
    if all(passed):
        print("OVERALL PASS")
        return 0

    print("OVERALL FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
