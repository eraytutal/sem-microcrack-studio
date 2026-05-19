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

from src import annotation_io, prediction_io  # noqa: E402
from src.annotation_io import get_dataset_status, save_annotation_json  # noqa: E402
from src.main_window import MainWindow  # noqa: E402
from src.prediction_io import (  # noqa: E402
    generate_dummy_polygon_predictions,
    load_predictions,
    save_predictions,
)
from src import main_window as main_window_module  # noqa: E402


IMAGE_SIZE = (400, 300)


@contextmanager
def temporary_data_dirs() -> Iterator[Path]:
    original_annotations_dir = annotation_io.ANNOTATIONS_DIR
    original_predictions_dir = prediction_io.PREDICTIONS_DIR
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        annotation_io.ANNOTATIONS_DIR = root / "annotations"
        prediction_io.PREDICTIONS_DIR = root / "predictions"
        try:
            yield root
        finally:
            annotation_io.ANNOTATIONS_DIR = original_annotations_dir
            prediction_io.PREDICTIONS_DIR = original_predictions_dir


@contextmanager
def suppress_message_boxes() -> Iterator[None]:
    original_warning = main_window_module.QMessageBox.warning
    main_window_module.QMessageBox.warning = lambda *args, **kwargs: None
    try:
        yield
    finally:
        main_window_module.QMessageBox.warning = original_warning


class StubStatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str, timeout: int = 0) -> None:
        self.messages.append(message)


class StubManualImageViewer:
    def __init__(self) -> None:
        self.annotations: list[dict[str, object]] = []

    def set_annotations(self, annotations: list[dict[str, object]]) -> None:
        self.annotations = [dict(annotation) for annotation in annotations]


class StubManualAnnotationPage:
    def __init__(self) -> None:
        self.image_viewer = StubManualImageViewer()
        self.review_status = ""
        self.unsaved_changes = False

    def annotation_save_context(self) -> dict[str, object]:
        return {"notes": "test metadata"}

    def set_image_review_status(self, status: str) -> None:
        self.review_status = status

    def set_unsaved_changes(self, has_unsaved_changes: bool) -> None:
        self.unsaved_changes = has_unsaved_changes


class StubAssistedImageViewer:
    def __init__(self) -> None:
        self.selected_data_id = ""
        self.clear_selection_count = 0

    def select_annotation_by_data_id(self, data_id: str) -> bool:
        self.selected_data_id = data_id
        return True

    def clear_selection(self) -> None:
        self.clear_selection_count += 1


class StubAssistedReviewPage:
    def __init__(self, selected_prediction_id: str = "pred_001") -> None:
        self._selected_prediction_id = selected_prediction_id
        self.image_viewer = StubAssistedImageViewer()
        self.selected_history: list[str] = []
        self.predictions: list[dict[str, object]] = []
        self.save_state = ""

    def selected_prediction_id(self) -> str:
        return self._selected_prediction_id

    def select_prediction(self, prediction_id: str) -> None:
        self._selected_prediction_id = prediction_id
        self.selected_history.append(prediction_id)

    def set_predictions(self, predictions: list[dict[str, object]]) -> None:
        self.predictions = [dict(prediction) for prediction in predictions]

    def set_review_save_state(self, state: str) -> None:
        self.save_state = state


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def fake_image_path(root: Path, name: str = "sample.png") -> str:
    image_dir = root / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image = image_dir / name
    image.write_bytes(b"fake image bytes")
    return str(image)


def manual_rectangles() -> list[dict[str, object]]:
    return [
        {
            "id": "ann_001",
            "label": "crack",
            "shape_type": "rectangle",
            "bbox": [10, 20, 30, 40],
            "source": "manual",
            "confidence": None,
            "exportable_to_mask": True,
            "status": "verified",
            "notes": "first",
        },
        {
            "id": "ann_002",
            "label": "scratch",
            "shape_type": "rectangle",
            "bbox": [50, 60, 70, 80],
            "source": "manual",
            "confidence": None,
            "exportable_to_mask": False,
            "status": "verified",
            "notes": "second",
        },
        {
            "id": "ann_003",
            "label": "pit",
            "shape_type": "rectangle",
            "bbox": [90, 100, 25, 35],
            "source": "manual",
            "confidence": None,
            "exportable_to_mask": True,
            "status": "verified",
            "notes": "third",
        },
    ]


def reviewed_predictions(image: str) -> list[dict[str, object]]:
    predictions = generate_dummy_polygon_predictions(image, IMAGE_SIZE)
    predictions[0]["status"] = "accepted"
    predictions[1]["status"] = "rejected"
    predictions[2]["status"] = "pending"
    return predictions


def make_window_double(
    image: str,
    predictions: list[dict[str, object]],
    manual_status: str = "unreviewed",
) -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window.current_image_path = image
    window.current_image_size = IMAGE_SIZE
    window.predictions_by_image = {image: predictions}
    window.review_dirty_by_image = {image: True}
    window.manual_annotations_by_image = {}
    window.manual_hidden_annotations_by_image = {}
    window.manual_image_status_by_image = {}
    window.manual_dirty_by_image = {}
    window.manual_annotation_page = StubManualAnnotationPage()
    window.assisted_review_page = StubAssistedReviewPage()
    window._current_manual_image_status = lambda: manual_status
    window._display_predictions = lambda items: window.assisted_review_page.set_predictions(items)
    window._update_review_save_state = lambda: None
    window.refresh_dataset_page = lambda: None
    window.status_bar = StubStatusBar()
    window.statusBar = lambda: window.status_bar
    return window


def save_review(image: str, predictions: list[dict[str, object]], manual_status: str = "unreviewed") -> bool:
    window = make_window_double(image, predictions, manual_status)
    return MainWindow.save_current_review(window)


def load_annotation_payload(image: str) -> dict[str, object]:
    data = annotation_io.load_annotation_json(image)
    check(isinstance(data, dict), "annotation JSON should exist")
    return data


def annotations_for_prediction(data: dict[str, object], prediction_id: str) -> list[dict[str, object]]:
    annotations = data.get("annotations", [])
    check(isinstance(annotations, list), "annotations should be a list")
    return [
        annotation
        for annotation in annotations
        if isinstance(annotation, dict) and annotation.get("prediction_id") == prediction_id
    ]


def test_prediction_save_does_not_overwrite_annotations() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "run_detection.png")
        save_annotation_json(image, IMAGE_SIZE, manual_rectangles(), {"notes": "manual"}, "annotated")
        before = annotation_io.get_annotation_path(image).read_text(encoding="utf-8")
        save_predictions(image, IMAGE_SIZE, generate_dummy_polygon_predictions(image, IMAGE_SIZE))
        after = annotation_io.get_annotation_path(image).read_text(encoding="utf-8")

    check_equal(after, before, "saving predictions must not modify annotation JSON")


def test_accept_does_not_write_annotations_before_save_review() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "accept_only.png")
        predictions = generate_dummy_polygon_predictions(image, IMAGE_SIZE)
        window = make_window_double(image, predictions)
        window.mark_review_dirty = lambda message="": window.review_dirty_by_image.__setitem__(image, True)
        MainWindow.accept_selected_prediction(window)
        annotation_exists = annotation_io.get_annotation_path(image).exists()

    check_equal(predictions[0]["status"], "accepted", "accept should update in-memory prediction status")
    check_equal(annotation_exists, False, "accept should not write annotation JSON before Save Review")


def test_reject_does_not_write_annotations() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "reject_only.png")
        predictions = generate_dummy_polygon_predictions(image, IMAGE_SIZE)
        window = make_window_double(image, predictions)
        window.mark_review_dirty = lambda message="": window.review_dirty_by_image.__setitem__(image, True)
        MainWindow.reject_selected_prediction(window)
        annotation_exists = annotation_io.get_annotation_path(image).exists()

    check_equal(predictions[0]["status"], "rejected", "reject should update in-memory prediction status")
    check_equal(annotation_exists, False, "reject should not write annotation JSON")


def test_a_preserve_existing_annotations() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "11.tif")
        save_annotation_json(image, IMAGE_SIZE, manual_rectangles(), {"notes": "metadata"}, "annotated")
        predictions = reviewed_predictions(image)
        result = save_review(image, predictions)
        data = load_annotation_payload(image)

    annotations = data["annotations"]
    prediction_ids = {annotation.get("prediction_id") for annotation in annotations}
    check_equal(result, True, "Save Review should succeed")
    check_equal(len(annotations), 4, "three manual annotations plus one accepted prediction")
    check_equal([item["id"] for item in annotations[:3]], ["ann_001", "ann_002", "ann_003"], "manual ids preserved")
    check("pred_001" in prediction_ids, "accepted pred_001 should be added")
    check("pred_002" not in prediction_ids, "rejected pred_002 should not be added")
    check("pred_003" not in prediction_ids, "pending pred_003 should not be added")


def test_b_duplicate_prevention() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "duplicate.png")
        save_annotation_json(image, IMAGE_SIZE, manual_rectangles(), {}, "annotated")
        predictions = reviewed_predictions(image)
        save_review(image, predictions)
        save_review(image, predictions)
        data = load_annotation_payload(image)

    accepted = annotations_for_prediction(data, "pred_001")
    check_equal(len(accepted), 1, "accepted prediction should appear once after repeated Save Review")
    check_equal(accepted[0]["id"], "ann_from_duplicate_pred_001", "accepted annotation id should be deterministic")


def test_c_polygon_preservation() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "polygon.png")
        save_annotation_json(image, IMAGE_SIZE, manual_rectangles(), {}, "annotated")
        predictions = reviewed_predictions(image)
        expected = predictions[0]
        save_review(image, predictions)
        data = load_annotation_payload(image)

    accepted = annotations_for_prediction(data, "pred_001")[0]
    check_equal(accepted["shape_type"], "polygon", "accepted annotation shape_type")
    check_equal(accepted["points"], expected["points"], "accepted annotation points")
    check_equal(accepted["bbox"], expected["bbox"], "accepted annotation bbox")
    check_equal(accepted["source"], "model", "accepted annotation source")
    check_equal(accepted["confidence"], expected["confidence"], "accepted annotation confidence")
    check_equal(accepted["status"], "verified", "accepted annotation status")
    check_equal(accepted["exportable_to_mask"], True, "accepted annotation exportable_to_mask")


def test_d_reject_never_becomes_annotation() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "reject_save.png")
        save_annotation_json(image, IMAGE_SIZE, manual_rectangles(), {}, "annotated")
        predictions = reviewed_predictions(image)
        save_review(image, predictions)
        data = load_annotation_payload(image)

    check_equal(annotations_for_prediction(data, "pred_002"), [], "rejected pred_002 should not become annotation")


def test_e_prediction_status_save_load() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "statuses.png")
        predictions = reviewed_predictions(image)
        save_predictions(image, IMAGE_SIZE, predictions)
        loaded = load_predictions(image)

    check_equal([prediction["status"] for prediction in loaded], ["accepted", "rejected", "pending"], "statuses persisted")


def test_f_no_defect_guard() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "no_defect.png")
        save_annotation_json(image, IMAGE_SIZE, [], {}, "reviewed_no_defect")
        predictions = generate_dummy_polygon_predictions(image, IMAGE_SIZE)
        accept_window = make_window_double(image, predictions, manual_status="reviewed_no_defect")
        accept_window.mark_review_dirty = lambda message="": accept_window.review_dirty_by_image.__setitem__(image, True)
        with suppress_message_boxes():
            MainWindow.accept_selected_prediction(accept_window)
        predictions[0]["status"] = "accepted"
        save_window = make_window_double(image, predictions, manual_status="reviewed_no_defect")
        with suppress_message_boxes():
            result = MainWindow.save_current_review(save_window)
        data = load_annotation_payload(image)

    check_equal(result, False, "Save Review should be blocked for no-defect image with accepted predictions")
    check_equal(data["image_status"], "reviewed_no_defect", "no-defect status should remain")
    check_equal(data["annotations"], [], "no-defect annotations should remain empty")


def test_g_dataset_status_ignores_predictions() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "predictions_only.png")
        predictions = reviewed_predictions(image)
        save_predictions(image, IMAGE_SIZE, predictions)
        status_data = get_dataset_status([image])

    check_equal(status_data["annotated_images"], 0, "predictions-only image should not count as annotated")
    check_equal(status_data["unreviewed_images"], 1, "predictions-only image should count as unreviewed")
    check_equal(status_data["rows"][0]["annotation_count"], 0, "predictions should not affect annotation count")


def test_cancel_changes_reverts_to_saved_predictions() -> None:
    with temporary_data_dirs() as root:
        image = fake_image_path(root, "cancel.png")
        predictions = reviewed_predictions(image)
        save_predictions(image, IMAGE_SIZE, predictions)
        unsaved = [dict(prediction) for prediction in predictions]
        unsaved[0]["status"] = "rejected"
        unsaved[1]["status"] = "accepted"
        window = make_window_double(image, unsaved)
        MainWindow.cancel_current_review_changes(window)
        restored_statuses = [prediction["status"] for prediction in window.predictions_by_image[image]]

    check_equal(restored_statuses, ["accepted", "rejected", "pending"], "cancel should reload saved prediction statuses")


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
        ("run detection predictions do not overwrite annotations", test_prediction_save_does_not_overwrite_annotations),
        ("accept does not write annotations before Save Review", test_accept_does_not_write_annotations_before_save_review),
        ("reject does not write annotations", test_reject_does_not_write_annotations),
        ("A preserve existing annotations", test_a_preserve_existing_annotations),
        ("B duplicate prevention", test_b_duplicate_prevention),
        ("C polygon preservation", test_c_polygon_preservation),
        ("D rejected prediction never becomes annotation", test_d_reject_never_becomes_annotation),
        ("E prediction status save/load", test_e_prediction_status_save_load),
        ("F no-defect guard", test_f_no_defect_guard),
        ("G dataset status ignores predictions", test_g_dataset_status_ignores_predictions),
        ("cancel changes reverts saved prediction JSON", test_cancel_changes_reverts_to_saved_predictions),
    ]
    passed = [run_test(name, test_func) for name, test_func in tests]
    if all(passed):
        print("OVERALL PASS")
        return 0

    print("OVERALL FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
