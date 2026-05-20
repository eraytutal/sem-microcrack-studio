from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PySide6.QtGui import QImage

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import annotation_io, prediction_io  # noqa: E402
from src.model_prediction_import import (  # noqa: E402
    DEFAULT_CLASS_MAP,
    import_prediction_folder_for_images,
    import_prediction_txt,
    summarize_import_results,
)
from src.prediction_io import generate_dummy_polygon_predictions, load_predictions, save_predictions  # noqa: E402


class TestFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise TestFailure(message)


def check_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise TestFailure(f"{message}: expected {expected!r}, got {actual!r}")


def _directory_snapshot(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    snapshot: dict[str, str] = {}
    for file_path in sorted(path.glob("*.json")):
        if not file_path.is_file():
            continue
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        snapshot[file_path.name] = digest
    return snapshot


@contextmanager
def real_data_guard() -> Iterator[None]:
    annotations_before = _directory_snapshot(PROJECT_ROOT / "data" / "annotations")
    predictions_before = _directory_snapshot(PROJECT_ROOT / "data" / "predictions")
    yield
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
def temporary_data_dirs(root: Path) -> Iterator[tuple[Path, Path]]:
    original_annotations_dir = annotation_io.ANNOTATIONS_DIR
    original_predictions_dir = prediction_io.PREDICTIONS_DIR
    annotation_io.ANNOTATIONS_DIR = root / "annotations"
    prediction_io.PREDICTIONS_DIR = root / "predictions"
    try:
        yield annotation_io.ANNOTATIONS_DIR, prediction_io.PREDICTIONS_DIR
    finally:
        annotation_io.ANNOTATIONS_DIR = original_annotations_dir
        prediction_io.PREDICTIONS_DIR = original_predictions_dir


def create_image(path: Path, width: int = 1000, height: int = 500) -> None:
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(0x202020)
    check(image.save(str(path)), f"failed to save temp image {path}")


def read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    check(isinstance(data, dict), f"{path} should contain a JSON object")
    return data


def test_a_import_writes_only_predictions() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "sample.png"
        label_path = root / "sample.txt"
        output_dir = root / "predictions"

        create_image(image_path)
        label_path.write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87\n",
            encoding="utf-8",
        )

        with temporary_data_dirs(root), real_data_guard():
            result = import_prediction_txt(image_path, label_path, DEFAULT_CLASS_MAP, output_dir)

        output_path = Path(str(result["output_path"]))
        payload = read_json(output_path)
        predictions = payload.get("predictions")
        check(isinstance(predictions, list), "prediction JSON should contain predictions list")
        check_equal(len(predictions), 1, "prediction count")
        prediction = predictions[0]
        check(isinstance(prediction, dict), "prediction entry should be a JSON object")
        check_equal(prediction.get("shape_type"), "polygon", "shape_type")
        check_equal(prediction.get("source"), "model_import", "source")
        check_equal(prediction.get("status"), "pending", "status")
        check_equal(prediction.get("points"), [[100.0, 100.0], [300.0, 100.0], [300.0, 200.0], [100.0, 200.0]], "points")
        check_equal(prediction.get("bbox"), [100.0, 100.0, 200.0, 100.0], "bbox")
        check_equal((root / "annotations").exists(), False, "annotation output dir should remain untouched")


def test_b_empty_invalid_txt_is_safe() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "invalid.png"
        label_path = root / "invalid.txt"
        output_dir = root / "predictions"

        create_image(image_path)
        label_path.write_text(
            "not a prediction\n0 0.5 0.5 0.2 0.1 0.91\n1 0.10 0.20\n",
            encoding="utf-8",
        )

        with temporary_data_dirs(root), real_data_guard():
            result = import_prediction_txt(image_path, label_path, DEFAULT_CLASS_MAP, output_dir)

        payload = read_json(Path(str(result["output_path"])))
        check_equal(payload.get("predictions"), [], "invalid-only import should write empty predictions")
        check(result.get("warnings"), "invalid-only import should report warnings")
        check_equal((root / "annotations").exists(), False, "invalid import should not write annotations")


def test_c_empty_and_whitespace_txt_are_safe() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "empty.png"
        empty_label_path = root / "empty.txt"
        whitespace_label_path = root / "whitespace.txt"
        output_dir = root / "predictions"

        create_image(image_path)
        empty_label_path.write_text("", encoding="utf-8")
        whitespace_label_path.write_text("  \n\t\n", encoding="utf-8")

        with temporary_data_dirs(root), real_data_guard():
            empty_result = import_prediction_txt(image_path, empty_label_path, DEFAULT_CLASS_MAP, output_dir)
            whitespace_result = import_prediction_txt(image_path, whitespace_label_path, DEFAULT_CLASS_MAP, output_dir)

        empty_payload = read_json(Path(str(empty_result["output_path"])))
        whitespace_payload = read_json(Path(str(whitespace_result["output_path"])))

        check_equal(empty_payload.get("predictions"), [], "empty label file should write empty predictions")
        check_equal(whitespace_payload.get("predictions"), [], "whitespace label file should write empty predictions")
        check_equal(empty_result["summary"]["empty_label_files"], 1, "empty summary count")
        check_equal(whitespace_result["summary"]["empty_label_files"], 1, "whitespace summary count")
        check_equal((root / "annotations").exists(), False, "empty import should not write annotations")


def test_d_folder_import_matches_loaded_images_only() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        label_dir = root / "labels"
        output_dir = root / "predictions"
        image_1 = image_dir / "1.png"
        image_2 = image_dir / "2.png"

        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        create_image(image_1)
        create_image(image_2)
        (label_dir / "1.txt").write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87",
            encoding="utf-8",
        )
        (label_dir / "2.txt").write_text(
            "1 0.50 0.50 0.60 0.50 0.60 0.60 0.50 0.60",
            encoding="utf-8",
        )
        (label_dir / "extra.txt").write_text(
            "0 0.10 0.10 0.20 0.10 0.20 0.20",
            encoding="utf-8",
        )

        with temporary_data_dirs(root), real_data_guard():
            results = import_prediction_folder_for_images(
                [image_1, image_2],
                label_dir,
                DEFAULT_CLASS_MAP,
                output_dir,
            )

        payload_1 = read_json(output_dir / "1.json")
        payload_2 = read_json(output_dir / "2.json")
        summary = summarize_import_results(results)

    check_equal(len(payload_1["predictions"]), 1, "1.png prediction count")
    check_equal(len(payload_2["predictions"]), 1, "2.png prediction count")
    check_equal(summary["images_processed"], 2, "folder import images processed")
    check_equal(summary["prediction_files_found"], 2, "folder import matching labels")
    check_equal(summary["unmatched_label_files"], 1, "folder import unmatched label count")
    check_equal((output_dir / "extra.json").exists(), False, "unmatched label should not create prediction JSON")
    check_equal((root / "annotations").exists(), False, "folder import should not write annotations")


def test_e_folder_import_missing_empty_invalid_and_unicode() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_dir = root / "images"
        label_dir = root / "labels"
        output_dir = root / "predictions"
        image_1 = image_dir / "1.png"
        image_2 = image_dir / "2.png"
        unicode_image = image_dir / "断裂.png"

        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        create_image(image_1)
        create_image(image_2)
        create_image(unicode_image)
        (label_dir / "1.txt").write_text("", encoding="utf-8")
        (label_dir / "断裂.txt").write_text(
            "0 0.10 0.20 0.30 0.20 0.30 0.40 0.10 0.40 0.87\n"
            "0 0.5 0.5 0.2 0.1 0.91",
            encoding="utf-8",
        )

        with temporary_data_dirs(root), real_data_guard():
            results = import_prediction_folder_for_images(
                [image_1, image_2, unicode_image],
                label_dir,
                DEFAULT_CLASS_MAP,
                output_dir,
            )

        payload_1 = read_json(output_dir / "1.json")
        payload_2 = read_json(output_dir / "2.json")
        unicode_payload = read_json(output_dir / "断裂.json")
        summary = summarize_import_results(results)

    check_equal(payload_1["predictions"], [], "empty label predictions")
    check_equal(payload_2["predictions"], [], "missing label predictions")
    check_equal(len(unicode_payload["predictions"]), 1, "unicode image valid prediction count")
    check_equal(summary["images_processed"], 3, "mixed folder images processed")
    check_equal(summary["prediction_files_found"], 2, "mixed folder matching labels")
    check_equal(summary["empty_label_files"], 1, "mixed folder empty labels")
    check_equal(summary["missing_label_files"], 1, "mixed folder missing labels")
    check_equal(summary["invalid_lines_skipped"], 1, "mixed folder invalid lines")
    check_equal(summary["imported_predictions"], 1, "mixed folder imported predictions")
    check_equal((root / "annotations").exists(), False, "mixed folder import should not write annotations")


def test_f_toolbar_and_folder_import_code_path_exists() -> None:
    assisted_source = (PROJECT_ROOT / "src" / "pages" / "assisted_review_page.py").read_text(encoding="utf-8")
    main_source = (PROJECT_ROOT / "src" / "main_window.py").read_text(encoding="utf-8")
    check('"Open Folder"' in assisted_source, "toolbar should include Open Folder")
    check('"Run Dummy Detection"' in assisted_source, "toolbar should rename dummy detection button")
    check('"Import Prediction Folder"' in assisted_source, "toolbar should include Import Prediction Folder")
    check('"Open Image"' not in assisted_source, "Assisted Review toolbar should not show Open Image")
    check("getExistingDirectory" in main_source, "prediction import should use folder picker")
    check("Please open an image folder before importing predictions." in main_source, "folder prerequisite message")


def test_g_overwrite_guard_code_path_exists() -> None:
    source = (PROJECT_ROOT / "src" / "main_window.py").read_text(encoding="utf-8")
    check("for image_path in self.image_paths" in source, "import path should check loaded image paths")
    check("prediction_path_for_image(image_path).exists()" in source, "import path should detect existing prediction JSON")
    check("_confirm_prediction_folder_import_replace()" in source, "import path should request folder replace confirmation")
    check("Existing prediction files may be replaced." in source, "folder replace confirmation message should exist")


def test_h_unsaved_review_guard_code_path_exists() -> None:
    source = (PROJECT_ROOT / "src" / "main_window.py").read_text(encoding="utf-8")
    start = source.index("def import_prediction_folder_for_current_images")
    end = source.index("def accept_selected_prediction", start)
    import_method = source[start:end]
    check("has_unsaved_review_changes()" in import_method, "import should check unsaved review changes")
    check("_handle_unsaved_review_changes_before_leaving" in import_method, "import should route through unsaved-review prompt")
    check("before importing predictions" in import_method, "unsaved-review prompt should reference import")


def test_i_dummy_workflow_still_writes_temp_predictions() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "dummy.png"
        create_image(image_path, width=320, height=240)

        with temporary_data_dirs(root), real_data_guard():
            predictions = generate_dummy_polygon_predictions(str(image_path), (320, 240))
            save_predictions(str(image_path), (320, 240), predictions)
            loaded = load_predictions(str(image_path))

        check_equal(len(loaded), 3, "dummy workflow prediction count")
        check_equal({item.get("source") for item in loaded}, {"dummy_model"}, "dummy source should be unchanged")
        check_equal((root / "annotations").exists(), False, "dummy workflow should not write annotations")


def test_j_summary_dialog_and_dialog_style_exist() -> None:
    main_window_source = (PROJECT_ROOT / "src" / "main_window.py").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "assets" / "themes" / "dark.qss").read_text(encoding="utf-8")
    check("Prediction Import Summary" in main_window_source, "folder import summary dialog should exist")
    check("Unmatched label files ignored" in main_window_source, "folder import summary should mention unmatched labels")
    check("QMessageBox QLabel" in stylesheet, "message box label style should exist")
    check("color: #dbe7f3;" in stylesheet, "message box text should use readable light color")


def run_test(name: str, func) -> bool:
    try:
        func()
    except Exception as error:
        print(f"FAIL {name}: {error}")
        return False
    print(f"PASS {name}")
    return True


def main() -> int:
    tests = [
        ("A import writes only predictions", test_a_import_writes_only_predictions),
        ("B empty/invalid txt safe", test_b_empty_invalid_txt_is_safe),
        ("C empty/whitespace txt safe", test_c_empty_and_whitespace_txt_are_safe),
        ("D folder import matches loaded images only", test_d_folder_import_matches_loaded_images_only),
        ("E folder import missing/empty/invalid/unicode", test_e_folder_import_missing_empty_invalid_and_unicode),
        ("F toolbar and folder import code path", test_f_toolbar_and_folder_import_code_path_exists),
        ("G overwrite guard code path", test_g_overwrite_guard_code_path_exists),
        ("H unsaved review guard code path", test_h_unsaved_review_guard_code_path_exists),
        ("I dummy workflow unaffected", test_i_dummy_workflow_still_writes_temp_predictions),
        ("J summary dialog and dialog style", test_j_summary_dialog_and_dialog_style_exist),
    ]
    results = [run_test(name, func) for name, func in tests]
    if all(results):
        print("All import prediction UI logic checks passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
