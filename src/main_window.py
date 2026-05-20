from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.annotation_io import get_dataset_status, load_annotation_json, save_annotation_json
from src.annotation_model import is_polygon_annotation, is_rectangle_annotation, normalize_annotation
from src.icons import icon
from src.model_prediction_import import (
    DEFAULT_CLASS_MAP,
    import_prediction_folder_for_images,
    summarize_import_results,
)
from src.pages.assisted_review_page import AssistedReviewPage
from src.pages.dataset_export_page import DatasetExportPage
from src.pages.manual_annotation_page import ManualAnnotationPage
from src.prediction_io import (
    generate_dummy_polygon_predictions,
    load_predictions,
    prediction_path_for_image,
    prediction_to_annotation,
    save_predictions,
)
from src.yolo_seg_export import DEFAULT_OUTPUT_DIR, export_yolo_seg_dataset


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SEM Microcrack Studio")
        self.setMinimumSize(1200, 750)
        self.setWindowIcon(icon("app", active=True))

        self.page_meta = [
            ("Assisted Review", "Model-assisted defect review and operator validation"),
            ("Manual Annotation", "Precise correction tools for SEM microcrack labels"),
            ("Dataset & Export", "Dataset status, quality checks, and export placeholders"),
        ]
        self.nav_buttons: list[QPushButton] = []
        self.current_folder_path: str | None = None
        self.image_paths: list[str] = []
        self.current_image_index: int = -1
        self.current_image_path: str | None = None
        self.current_image_size: tuple[int, int] | None = None
        self.manual_annotations_by_image: dict[str, list[dict[str, object]]] = {}
        self.manual_hidden_annotations_by_image: dict[str, list[dict[str, object]]] = {}
        self.manual_image_status_by_image: dict[str, str] = {}
        self.manual_dirty_by_image: dict[str, bool] = {}
        self.predictions_by_image: dict[str, list[dict[str, object]]] = {}
        self.review_dirty_by_image: dict[str, bool] = {}

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_workspace(), 1)
        self.setCentralWidget(root)

        self._build_status_bar()
        self.switch_page(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(8)

        brand_icon = QLabel()
        brand_icon.setPixmap(icon("app", active=True).pixmap(26, 26))
        brand_title = QLabel("SEM Studio")
        brand_title.setObjectName("sidebarBrand")
        brand_subtitle = QLabel("Microcrack review")
        brand_subtitle.setObjectName("sidebarSubtitle")

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(brand_icon)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand_row.addLayout(brand_text)
        layout.addLayout(brand_row)
        layout.addSpacing(12)

        nav_items = [
            ("Assisted Review", "assisted"),
            ("Manual Annotation", "manual"),
            ("Dataset", "export"),
        ]
        for index, (label, icon_name) in enumerate(nav_items):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setIcon(icon(icon_name))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=index: self.switch_page(page))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        footer = QLabel("Milestone 1 UI shell")
        footer.setObjectName("sidebarFooter")
        layout.addWidget(footer)
        return sidebar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("topHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(14)

        title_column = QVBoxLayout()
        title_column.setSpacing(3)

        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("pageSubtitle")

        title_column.addWidget(self.page_title)
        title_column.addWidget(self.page_subtitle)
        header_layout.addLayout(title_column)
        header_layout.addStretch(1)

        layout.addWidget(header)

        self.stack = QStackedWidget()
        self.assisted_review_page = AssistedReviewPage()
        self.manual_annotation_page = ManualAnnotationPage()
        self.dataset_export_page = DatasetExportPage()
        self.assisted_review_page.open_image_requested.connect(self.open_image)
        self.assisted_review_page.open_folder_requested.connect(self.open_image_folder)
        self.assisted_review_page.previous_image_requested.connect(self.load_previous_image)
        self.assisted_review_page.next_image_requested.connect(self.load_next_image)
        self.assisted_review_page.run_detection_requested.connect(self.run_dummy_detection)
        self.assisted_review_page.import_predictions_requested.connect(self.import_prediction_folder_for_current_images)
        self.assisted_review_page.save_review_requested.connect(self.save_current_review)
        self.assisted_review_page.cancel_review_changes_requested.connect(self.cancel_current_review_changes)
        self.assisted_review_page.accept_prediction_requested.connect(self.accept_selected_prediction)
        self.assisted_review_page.reject_prediction_requested.connect(self.reject_selected_prediction)
        self.assisted_review_page.prediction_selected.connect(self.select_assisted_prediction)
        self.manual_annotation_page.previous_image_requested.connect(self.load_previous_image)
        self.manual_annotation_page.next_image_requested.connect(self.load_next_image)
        self.manual_annotation_page.save_annotation_requested.connect(self.save_current_annotation_json)
        self.manual_annotation_page.mark_no_defect_requested.connect(self.mark_current_image_no_defect)
        self.manual_annotation_page.clear_no_defect_requested.connect(self.clear_current_image_no_defect)
        self.manual_annotation_page.annotation_changed.connect(self.mark_current_image_dirty)
        self.dataset_export_page.refresh_requested.connect(self.refresh_dataset_page)
        self.dataset_export_page.browse_yolo_output_requested.connect(self.browse_yolo_export_output_dir)
        self.dataset_export_page.export_yolo_requested.connect(self.export_yolo_seg_dataset_from_ui)
        self.dataset_export_page.set_yolo_output_dir(str(DEFAULT_OUTPUT_DIR))
        self.stack.addWidget(self.assisted_review_page)
        self.stack.addWidget(self.manual_annotation_page)
        self.stack.addWidget(self.dataset_export_page)
        layout.addWidget(self.stack, 1)

        return workspace

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.setObjectName("statusBar")
        self.ready_label = QLabel("Ready")
        self.image_status_label = QLabel("")
        self.current_page_label = QLabel()
        status.addWidget(self.ready_label)
        status.addWidget(self.image_status_label, 1)
        status.addPermanentWidget(self.current_page_label)
        self.setStatusBar(status)

    def open_image(self) -> None:
        if not self._prepare_for_image_switch():
            return

        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SEM Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)",
        )
        if not image_path:
            return

        self.current_folder_path = str(Path(image_path).parent)
        self.image_paths = [image_path]
        self.current_image_index = 0
        self.load_image(image_path)

    def open_image_folder(self) -> None:
        if not self._prepare_for_image_switch():
            return

        folder_path = QFileDialog.getExistingDirectory(self, "Open SEM Image Folder")
        if not folder_path:
            return

        image_paths = self._collect_image_paths(folder_path)
        if not image_paths:
            QMessageBox.warning(
                self,
                "No Images Found",
                "No supported SEM image files were found in the selected folder.",
            )
            return

        self.current_folder_path = folder_path
        self.image_paths = image_paths
        self.current_image_index = 0
        self.load_image_at_index(self.current_image_index)
        self.refresh_dataset_page()

    def open_folder(self) -> None:
        self.open_image_folder()

    def load_image(self, image_path: str) -> None:
        self._save_current_manual_annotations()
        try:
            image_size = self.assisted_review_page.image_viewer.load_image(image_path)
            self.manual_annotation_page.image_viewer.load_image(image_path)
        except ValueError as error:
            QMessageBox.critical(self, "Image Loading Failed", str(error))
            return

        self.current_image_path = image_path
        self.current_image_size = (image_size.width(), image_size.height())
        self._restore_manual_annotations(image_path)
        self._restore_predictions(image_path)
        if image_path in self.image_paths:
            self.current_image_index = self.image_paths.index(image_path)
        self.update_navigation_state()
        self.refresh_dataset_page()
        self._update_status_bar()

    def load_image_at_index(self, index: int) -> None:
        if not 0 <= index < len(self.image_paths):
            return

        if index != self.current_image_index and not self._prepare_for_image_switch():
            return

        self.current_image_index = index
        self.load_image(self.image_paths[index])

    def load_previous_image(self) -> None:
        if not self.image_paths:
            return

        next_index = max(0, self.current_image_index - 1)
        self.load_image_at_index(next_index)

    def load_next_image(self) -> None:
        if not self.image_paths:
            return

        next_index = min(len(self.image_paths) - 1, self.current_image_index + 1)
        self.load_image_at_index(next_index)

    def update_navigation_state(self) -> None:
        filename = Path(self.current_image_path).name if self.current_image_path else "No image loaded"
        total_count = len(self.image_paths)
        display_index = self.current_image_index + 1 if total_count and self.current_image_index >= 0 else 0
        can_go_previous = total_count > 1 and self.current_image_index > 0
        can_go_next = total_count > 1 and 0 <= self.current_image_index < total_count - 1

        for page in (self.assisted_review_page, self.manual_annotation_page):
            page.set_navigation_state(filename, display_index, total_count, can_go_previous, can_go_next)

    def refresh_dataset_page(self) -> None:
        self.dataset_export_page.update_dataset_status(get_dataset_status(self.image_paths))

    def save_current_annotation_json(self) -> None:
        self.save_current_image_annotations()

    def browse_yolo_export_output_dir(self) -> None:
        current_output = str(self.dataset_export_page.yolo_export_settings().get("output_dir") or DEFAULT_OUTPUT_DIR)
        folder_path = QFileDialog.getExistingDirectory(self, "Select YOLO-Seg Export Folder", current_output)
        if folder_path:
            self.dataset_export_page.set_yolo_output_dir(folder_path)

    def export_yolo_seg_dataset_from_ui(self, settings: dict[str, object]) -> None:
        if not self._prepare_for_leaving_current_image():
            return

        image_folder = self.current_folder_path
        if not image_folder:
            image_folder = QFileDialog.getExistingDirectory(self, "Select Source Image Folder")
            if not image_folder:
                return

        output_dir = self._resolved_output_dir(str(settings.get("output_dir") or DEFAULT_OUTPUT_DIR))
        if output_dir.exists() and any(output_dir.iterdir()) and not self._confirm_yolo_export_replace():
            return

        try:
            report = export_yolo_seg_dataset(
                image_folder=image_folder,
                output_dir=output_dir,
                train_percent=int(settings.get("train_percent", 70)),
                val_percent=int(settings.get("val_percent", 20)),
                test_percent=int(settings.get("test_percent", 10)),
                seed=int(settings.get("seed", 42)),
                include_no_defect=bool(settings.get("include_no_defect", True)),
                include_uncertain=bool(settings.get("include_uncertain", False)),
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "YOLO Export Failed", str(error))
            return

        QMessageBox.information(
            self,
            "YOLO Export Complete",
            "\n".join(
                [
                    f"Output: {output_dir}",
                    f"Images exported: {report.get('images_exported', 0)}",
                    f"Labels written: {report.get('labels_written', 0)}",
                    f"No Defect negatives: {report.get('no_defect_images_exported', 0)}",
                    f"Skipped unreviewed: {report.get('skipped_unreviewed', 0)}",
                ]
            ),
        )
        self.statusBar().showMessage(f"Exported YOLO-Seg dataset to {output_dir}.", 5000)

    def run_dummy_detection(self) -> None:
        if not self.current_image_path or not self.current_image_size:
            QMessageBox.warning(self, "No Image Loaded", "Open an image folder before running dummy detection.")
            return
        if self.has_unsaved_review_changes():
            self._handle_unsaved_review_changes_before_leaving(
                "You have unsaved prediction review changes.\nSave or cancel these changes before running detection again?"
            )
            return

        predictions = generate_dummy_polygon_predictions(self.current_image_path, self.current_image_size)
        self.predictions_by_image[self.current_image_path] = predictions
        save_predictions(self.current_image_path, self.current_image_size, predictions)
        self.review_dirty_by_image[self.current_image_path] = False
        self._display_predictions(predictions)
        self._update_review_save_state()
        filename = Path(self.current_image_path).name
        self.statusBar().showMessage(f"Generated dummy predictions for {filename}.", 4000)

    def import_prediction_folder_for_current_images(self) -> None:
        if not self.current_folder_path or not self.image_paths or not self.current_image_path:
            QMessageBox.warning(
                self,
                "No Image Folder Loaded",
                "Please open an image folder before importing predictions.",
            )
            return

        if self.has_unsaved_review_changes():
            self._handle_unsaved_review_changes_before_leaving(
                "You have unsaved prediction review changes.\nSave or cancel these changes before importing predictions?"
            )
            return

        existing_prediction_files = [
            prediction_path_for_image(image_path)
            for image_path in self.image_paths
            if prediction_path_for_image(image_path).exists()
        ]
        if existing_prediction_files and not self._confirm_prediction_folder_import_replace():
            return

        label_folder_path = QFileDialog.getExistingDirectory(
            self,
            "Import Prediction Label Folder",
        )
        if not label_folder_path:
            return

        try:
            import_results = import_prediction_folder_for_images(
                self.image_paths,
                label_folder_path,
                DEFAULT_CLASS_MAP,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Prediction Import Failed", str(error))
            return

        for image_path in self.image_paths:
            self.review_dirty_by_image[image_path] = False
            self.predictions_by_image[image_path] = load_predictions(image_path)

        predictions = load_predictions(self.current_image_path)
        self.predictions_by_image[self.current_image_path] = predictions
        self._display_predictions(predictions)
        self.assisted_review_page.image_viewer.clear_selection()
        self._update_review_save_state()

        summary = summarize_import_results(import_results)
        self._show_prediction_folder_import_summary(summary)
        self.statusBar().showMessage(
            f"Imported {summary['imported_predictions']} predictions from label folder.",
            5000,
        )

    def accept_selected_prediction(self) -> None:
        prediction = self._selected_prediction()
        if prediction is None or str(prediction.get("status") or "pending") != "pending":
            return

        if self._current_manual_image_status() == "reviewed_no_defect":
            QMessageBox.warning(
                self,
                "No Defect Mark Active",
                "This image is marked as No Defect. Clear No Defect in Manual Annotation before accepting predictions.",
            )
            return

        prediction["status"] = "accepted"
        self.mark_review_dirty("Prediction accepted. Unsaved review changes.")

    def reject_selected_prediction(self) -> None:
        prediction = self._selected_prediction()
        if prediction is None or str(prediction.get("status") or "pending") != "pending":
            return

        prediction["status"] = "rejected"
        self.mark_review_dirty("Prediction rejected. Unsaved review changes.")

    def select_assisted_prediction(self, prediction_id: str) -> None:
        self.assisted_review_page.image_viewer.select_annotation_by_data_id(prediction_id)

    def save_current_review(self) -> bool:
        if not self.current_image_path or not self.current_image_size:
            QMessageBox.warning(self, "No Image Loaded", "Open an image before saving review decisions.")
            return False

        predictions = self.predictions_by_image.get(self.current_image_path, [])
        if not predictions:
            self._update_review_save_state()
            return True

        if self._current_manual_image_status() == "reviewed_no_defect" and any(
            str(prediction.get("status") or "") == "accepted" for prediction in predictions
        ):
            QMessageBox.warning(
                self,
                "No Defect Mark Active",
                "This image is marked as No Defect. Clear No Defect in Manual Annotation before accepting predictions.",
            )
            return False

        save_predictions(self.current_image_path, self.current_image_size, predictions)
        self._append_accepted_predictions_to_annotations(predictions)
        self.review_dirty_by_image[self.current_image_path] = False
        self._display_predictions(predictions)
        self._update_review_save_state()
        self.refresh_dataset_page()
        filename = Path(self.current_image_path).name
        self.statusBar().showMessage(f"Saved review decisions for {filename}.", 4000)
        return True

    def cancel_current_review_changes(self) -> None:
        if not self.current_image_path:
            return

        predictions = load_predictions(self.current_image_path)
        self.predictions_by_image[self.current_image_path] = predictions
        self.review_dirty_by_image[self.current_image_path] = False
        self._display_predictions(predictions)
        self.assisted_review_page.image_viewer.clear_selection()
        self._update_review_save_state()

    def save_current_image_annotations(self) -> bool:
        if not self.current_image_path or not self.current_image_size:
            QMessageBox.warning(self, "No Image Loaded", "Open an image before saving annotations.")
            return False

        if self.manual_annotation_page.image_viewer.has_pending_annotation():
            QMessageBox.warning(
                self,
                "Pending Annotation",
                "Confirm or discard the current annotation before saving.",
            )
            return False

        annotations = self.manual_annotation_page.image_viewer.get_annotations()
        hidden_annotations = self.manual_hidden_annotations_by_image.get(self.current_image_path, [])
        annotations = [*annotations, *hidden_annotations]
        image_status = self._current_manual_image_status()
        self.manual_annotations_by_image[self.current_image_path] = annotations
        self.manual_image_status_by_image[self.current_image_path] = image_status
        annotation_path = save_annotation_json(
            self.current_image_path,
            self.current_image_size,
            annotations,
            self.manual_annotation_page.annotation_save_context(),
            image_status,
        )
        self.clear_current_image_dirty()
        filename = Path(self.current_image_path).name
        self.statusBar().showMessage(f"Saved annotations for {filename}.", 4000)
        self.refresh_dataset_page()
        return True

    def mark_current_image_no_defect(self) -> None:
        if not self.current_image_path:
            QMessageBox.warning(self, "No Image Loaded", "Open an image before marking review status.")
            return

        viewer = self.manual_annotation_page.image_viewer
        if viewer.has_pending_annotation():
            QMessageBox.warning(
                self,
                "Pending Annotation",
                "Confirm or discard the current annotation before marking this image as No Defect.",
            )
            return

        hidden_annotations = self.manual_hidden_annotations_by_image.get(self.current_image_path, [])
        if viewer.confirmed_annotation_count() > 0 or hidden_annotations:
            QMessageBox.warning(
                self,
                "Annotations Present",
                "Remove confirmed annotations before marking this image as No Defect.",
            )
            return

        viewer.clear_annotations()
        self.manual_annotations_by_image[self.current_image_path] = []
        self.manual_hidden_annotations_by_image[self.current_image_path] = []
        self.manual_image_status_by_image[self.current_image_path] = "reviewed_no_defect"
        self.manual_annotation_page.set_image_review_status("reviewed_no_defect")
        self.mark_current_image_dirty("No Defect status changed. Unsaved changes.")

    def clear_current_image_no_defect(self) -> None:
        if not self.current_image_path:
            return

        self.manual_image_status_by_image[self.current_image_path] = "unreviewed"
        self.manual_annotation_page.set_image_review_status("unreviewed")
        self.mark_current_image_dirty("No Defect status changed. Unsaved changes.")

    def mark_current_image_dirty(self, message: str = "Unsaved changes.") -> None:
        if not self.current_image_path:
            return

        self.manual_dirty_by_image[self.current_image_path] = True
        self._save_current_manual_annotations()
        self.manual_annotation_page.set_unsaved_changes(True)
        self.statusBar().showMessage(message, 4000)

    def mark_review_dirty(self, message: str = "Unsaved review changes.") -> None:
        if not self.current_image_path:
            return

        self.review_dirty_by_image[self.current_image_path] = True
        selected_id = self.assisted_review_page.selected_prediction_id()
        self._display_predictions(self.predictions_by_image.get(self.current_image_path, []))
        if selected_id:
            self.assisted_review_page.select_prediction(selected_id)
            self.assisted_review_page.image_viewer.select_annotation_by_data_id(selected_id)
        self._update_review_save_state()
        self.statusBar().showMessage(message, 4000)

    def clear_current_image_dirty(self) -> None:
        if not self.current_image_path:
            return

        self.manual_dirty_by_image[self.current_image_path] = False
        self.manual_annotation_page.set_unsaved_changes(False)

    def has_unsaved_changes(self) -> bool:
        return bool(self.current_image_path and self.manual_dirty_by_image.get(self.current_image_path, False))

    def has_unsaved_review_changes(self) -> bool:
        return bool(self.current_image_path and self.review_dirty_by_image.get(self.current_image_path, False))

    def closeEvent(self, event) -> None:
        if self._confirm_close_with_unsaved_changes():
            event.accept()
        else:
            event.ignore()

    def switch_page(self, index: int) -> None:
        if index != self.stack.currentIndex() and not self._prepare_for_leaving_current_image():
            return

        self.stack.setCurrentIndex(index)
        page_name, subtitle = self.page_meta[index]
        self.page_title.setText(page_name)
        self.page_subtitle.setText(subtitle)
        self._update_status_bar(page_name)

        icon_names = ["assisted", "manual", "export"]
        for button_index, button in enumerate(self.nav_buttons):
            active = button_index == index
            button.setProperty("active", active)
            button.setIcon(icon(icon_names[button_index], active=active))
            button.style().unpolish(button)
            button.style().polish(button)

    def _update_status_bar(self, page_name: str | None = None) -> None:
        if page_name is None:
            page_name = self.page_meta[self.stack.currentIndex()][0]

        if self.current_image_path and self.current_image_size:
            filename = Path(self.current_image_path).name
            width, height = self.current_image_size
            index_text = self._image_index_status()
            self.image_status_label.setText(f"{filename} | {width} x {height} | {index_text}")
        else:
            self.image_status_label.setText("No image loaded")

        self.current_page_label.setText(page_name)

    def _prepare_for_image_switch(self) -> bool:
        return self._prepare_for_leaving_current_image()

    def _prepare_for_leaving_current_image(self) -> bool:
        if self.has_unsaved_review_changes():
            self._handle_unsaved_review_changes_before_leaving(
                "You have unsaved prediction review changes.\nSave or cancel these changes before leaving?"
            )
            return False

        if self.manual_annotation_page.image_viewer.has_pending_annotation():
            QMessageBox.warning(
                self,
                "Pending Annotation",
                "You have a pending annotation.\nAdd or discard it before leaving.",
            )
            return False

        if not self.has_unsaved_changes():
            return True

        choice = self._ask_save_or_cancel_changes(
            "Unsaved Changes",
            "You have unsaved changes for this image.\nSave or cancel these changes before leaving?",
        )
        if choice == "save":
            self.save_current_image_annotations()
        elif choice == "cancel_changes":
            self.discard_current_image_unsaved_changes()
        return False

    def _confirm_close_with_unsaved_changes(self) -> bool:
        if self.has_unsaved_review_changes():
            choice = self._ask_save_or_cancel_changes(
                "Unsaved Review Changes",
                "You have unsaved prediction review changes.\nSave or cancel these changes before closing?",
            )
            if choice == "save":
                return self.save_current_review()
            if choice == "cancel_changes":
                self.cancel_current_review_changes()
                return True
            return False

        if self.manual_annotation_page.image_viewer.has_pending_annotation():
            QMessageBox.warning(
                self,
                "Pending Annotation",
                "You have a pending annotation.\nAdd or discard it before leaving.",
            )
            return False

        if not self.has_unsaved_changes():
            return True

        choice = self._ask_save_or_cancel_changes(
            "Unsaved Changes",
            "You have unsaved changes.\nSave or cancel these changes before closing?",
        )
        if choice == "save":
            return self.save_current_image_annotations()
        if choice == "cancel_changes":
            self.discard_current_image_unsaved_changes()
            return True
        return False

    def _ask_save_or_cancel_changes(self, title: str, message: str) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        save_button = dialog.addButton("Save Changes", QMessageBox.AcceptRole)
        cancel_changes_button = dialog.addButton("Cancel Changes", QMessageBox.DestructiveRole)
        dialog.setDefaultButton(save_button)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked is save_button:
            return "save"
        if clicked is cancel_changes_button:
            return "cancel_changes"
        return "cancel_changes"

    def _confirm_prediction_folder_import_replace(self) -> bool:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("Existing Predictions")
        dialog.setText("Existing prediction files may be replaced.\nReplace predictions for matched images?")
        replace_button = dialog.addButton("Replace", QMessageBox.AcceptRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() is replace_button

    def _confirm_yolo_export_replace(self) -> bool:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("Existing Export Output")
        dialog.setText("Existing YOLO export output may be replaced.\nContinue export?")
        export_button = dialog.addButton("Export", QMessageBox.AcceptRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() is export_button

    def _resolved_output_dir(self, output_dir: str) -> Path:
        path = Path(output_dir).expanduser()
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parent.parent / path

    def _show_prediction_folder_import_summary(self, summary: dict[str, int]) -> None:
        QMessageBox.information(
            self,
            "Prediction Import Summary",
            "\n".join(
                [
                    f"Images in current folder: {summary.get('images_processed', 0)}",
                    f"Matching label files found: {summary.get('prediction_files_found', 0)}",
                    f"Missing label files: {summary.get('missing_label_files', 0)}",
                    f"Empty label files: {summary.get('empty_label_files', 0)}",
                    f"Unmatched label files ignored: {summary.get('unmatched_label_files', 0)}",
                    f"Imported predictions: {summary.get('imported_predictions', 0)}",
                    f"Invalid/unsupported lines skipped: {summary.get('invalid_lines_skipped', 0)}",
                ]
            ),
        )

    def _handle_unsaved_review_changes_before_leaving(self, message: str) -> None:
        choice = self._ask_save_or_cancel_changes("Unsaved Review Changes", message)
        if choice == "save":
            self.save_current_review()
        elif choice == "cancel_changes":
            self.cancel_current_review_changes()

    def discard_current_image_unsaved_changes(self) -> None:
        if not self.current_image_path:
            return

        annotations, hidden_annotations, image_status = self._load_manual_state_from_json(self.current_image_path)
        self.manual_annotations_by_image[self.current_image_path] = annotations
        self.manual_hidden_annotations_by_image[self.current_image_path] = hidden_annotations
        self.manual_image_status_by_image[self.current_image_path] = image_status
        self.manual_dirty_by_image[self.current_image_path] = False
        self.manual_annotation_page.image_viewer.set_annotations(annotations)
        self.manual_annotation_page.image_viewer.clear_selection()
        self.manual_annotation_page.set_image_review_status(image_status)
        self.manual_annotation_page.set_unsaved_changes(False)

    def _image_index_status(self) -> str:
        if self.image_paths and self.current_image_index >= 0:
            return f"{self.current_image_index + 1} / {len(self.image_paths)}"

        return "1 / 1"

    def _collect_image_paths(self, folder_path: str) -> list[str]:
        folder = Path(folder_path)
        return [
            str(path)
            for path in sorted(folder.iterdir(), key=lambda item: item.name.lower())
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]

    def _save_current_manual_annotations(self) -> None:
        if not self.current_image_path:
            return

        self.manual_annotations_by_image[self.current_image_path] = (
            self.manual_annotation_page.image_viewer.get_annotations()
        )
        self.manual_image_status_by_image[self.current_image_path] = self._current_manual_image_status()

    def _restore_manual_annotations(self, image_path: str) -> None:
        if image_path in self.manual_annotations_by_image:
            annotations = self.manual_annotations_by_image[image_path]
            hidden_annotations = self.manual_hidden_annotations_by_image.get(image_path, [])
            image_status = self.manual_image_status_by_image.get(
                image_path,
                "annotated" if annotations or hidden_annotations else "unreviewed",
            )
        else:
            annotations, hidden_annotations, image_status = self._load_manual_state_from_json(image_path)
            self.manual_annotations_by_image[image_path] = annotations
            self.manual_hidden_annotations_by_image[image_path] = hidden_annotations
            self.manual_image_status_by_image[image_path] = image_status

        self.manual_annotation_page.image_viewer.set_annotations(annotations)
        self.manual_annotation_page.set_image_review_status(image_status)
        self.manual_annotation_page.set_unsaved_changes(self.manual_dirty_by_image.get(image_path, False))

    def _restore_predictions(self, image_path: str) -> None:
        self.predictions_by_image[image_path] = load_predictions(image_path)
        self.review_dirty_by_image[image_path] = False
        self._display_predictions(self.predictions_by_image[image_path])
        self._update_review_save_state()

    def _display_predictions(self, predictions: list[dict[str, object]]) -> None:
        self.assisted_review_page.image_viewer.set_prediction_overlays(predictions)
        self.assisted_review_page.set_predictions(predictions)

    def _selected_prediction(self) -> dict[str, object] | None:
        if not self.current_image_path:
            return None

        prediction_id = self.assisted_review_page.selected_prediction_id()
        if not prediction_id:
            return None

        for prediction in self.predictions_by_image.get(self.current_image_path, []):
            if str(prediction.get("id") or "") == prediction_id:
                return prediction
        return None

    def _save_and_display_current_predictions(self) -> None:
        if not self.current_image_path or not self.current_image_size:
            return

        predictions = self.predictions_by_image.get(self.current_image_path, [])
        selected_id = self.assisted_review_page.selected_prediction_id()
        save_predictions(self.current_image_path, self.current_image_size, predictions)
        self._display_predictions(predictions)
        if selected_id:
            self.assisted_review_page.select_prediction(selected_id)
            self.assisted_review_page.image_viewer.select_annotation_by_data_id(selected_id)

    def _update_review_save_state(self) -> None:
        if not self.current_image_path:
            self.assisted_review_page.set_review_save_state("none")
        elif self.review_dirty_by_image.get(self.current_image_path, False):
            self.assisted_review_page.set_review_save_state("unsaved")
        elif self.predictions_by_image.get(self.current_image_path) or prediction_path_for_image(
            self.current_image_path
        ).exists():
            self.assisted_review_page.set_review_save_state("saved")
        else:
            self.assisted_review_page.set_review_save_state("none")

    def _append_accepted_predictions_to_annotations(self, predictions: list[dict[str, object]]) -> None:
        if not self.current_image_path or not self.current_image_size:
            return

        existing_data = load_annotation_json(self.current_image_path) or {}
        raw_annotations = existing_data.get("annotations", [])
        if not isinstance(raw_annotations, list):
            raw_annotations = []

        annotations: list[dict[str, object]] = [
            dict(annotation) for annotation in raw_annotations if isinstance(annotation, dict)
        ]
        prediction_id_index: dict[str, dict[str, object]] = {}
        annotation_id_index: dict[str, dict[str, object]] = {}
        for annotation in annotations:
            prediction_id = str(annotation.get("prediction_id") or "")
            annotation_id = str(annotation.get("id") or "")
            if prediction_id:
                prediction_id_index[prediction_id] = annotation
            if annotation_id:
                annotation_id_index[annotation_id] = annotation

        image_stem = Path(self.current_image_path).stem
        changed = False
        for prediction in predictions:
            if str(prediction.get("status") or "") != "accepted":
                continue

            prediction_id = str(prediction.get("id") or "")
            annotation_id = f"ann_from_{image_stem}_{prediction_id}"
            annotation = prediction_to_annotation(prediction, annotation_id)
            existing = prediction_id_index.get(prediction_id) or annotation_id_index.get(annotation_id)
            if existing is not None:
                existing.update(annotation)
            else:
                annotations.append(annotation)
                prediction_id_index[prediction_id] = annotation
                annotation_id_index[annotation_id] = annotation
            changed = True

        if not changed:
            return

        save_annotation_json(
            self.current_image_path,
            self.current_image_size,
            annotations,
            self._annotation_metadata_for_current_image(),
            "annotated",
        )
        display_annotations, hidden_annotations, image_status = self._load_manual_state_from_json(
            self.current_image_path
        )
        self.manual_annotations_by_image[self.current_image_path] = display_annotations
        self.manual_hidden_annotations_by_image[self.current_image_path] = hidden_annotations
        self.manual_image_status_by_image[self.current_image_path] = "annotated"
        self.manual_dirty_by_image[self.current_image_path] = False
        self.manual_annotation_page.image_viewer.set_annotations(display_annotations)
        self.manual_annotation_page.set_image_review_status("annotated")
        self.manual_annotation_page.set_unsaved_changes(False)

    def _next_annotation_id(self, annotations: list[dict[str, object]]) -> str:
        max_index = 0
        for annotation in annotations:
            raw_id = str(annotation.get("id") or "")
            if raw_id.startswith("ann_"):
                try:
                    max_index = max(max_index, int(raw_id.removeprefix("ann_")))
                except ValueError:
                    continue
        return f"ann_{max_index + 1:03d}"

    def _annotation_metadata_for_current_image(self) -> dict[str, object]:
        if not self.current_image_path:
            return {}

        data = load_annotation_json(self.current_image_path)
        if isinstance(data, dict) and isinstance(data.get("metadata"), dict):
            return data["metadata"]
        return self.manual_annotation_page.annotation_save_context()

    def _load_manual_state_from_json(
        self,
        image_path: str,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
        data = load_annotation_json(image_path)
        if not data:
            return [], [], "unreviewed"

        annotations: list[dict[str, object]] = []
        hidden_annotations: list[dict[str, object]] = []
        raw_annotations = data.get("annotations", [])
        if not isinstance(raw_annotations, list):
            raw_annotations = []

        for index, raw_annotation in enumerate(raw_annotations, start=1):
            if not isinstance(raw_annotation, dict):
                continue

            annotation = normalize_annotation(raw_annotation, fallback_id=f"ann_{index:03d}")
            if is_polygon_annotation(annotation):
                points = annotation.get("points", [])
                if isinstance(points, list) and len(points) >= 3:
                    annotations.append(annotation)
                else:
                    hidden_annotations.append(annotation)
                continue

            if not is_rectangle_annotation(annotation):
                hidden_annotations.append(annotation)
                continue

            bbox = annotation.get("bbox", [])
            x, y, width, height = bbox
            annotations.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "width": float(width),
                    "height": float(height),
                    "label": str(annotation.get("label") or "crack"),
                    "shape_type": "rectangle",
                    "source": str(annotation.get("source") or "manual"),
                    "confidence": annotation.get("confidence"),
                    "exportable_to_mask": bool(annotation.get("exportable_to_mask", True)),
                    "status": str(annotation.get("status") or "verified"),
                    "notes": str(annotation.get("notes") or ""),
                }
            )

        raw_status = str(data.get("image_status") or "")
        if raw_status in {"unreviewed", "annotated", "reviewed_no_defect"}:
            image_status = raw_status
        else:
            image_status = "annotated" if annotations or hidden_annotations else "unreviewed"

        if annotations or hidden_annotations:
            image_status = "annotated"
        elif image_status != "reviewed_no_defect":
            image_status = "unreviewed"

        return annotations, hidden_annotations, image_status

    def _current_manual_image_status(self) -> str:
        viewer = self.manual_annotation_page.image_viewer
        has_hidden_annotations = bool(
            self.current_image_path
            and self.manual_hidden_annotations_by_image.get(self.current_image_path, [])
        )
        if viewer.confirmed_annotation_count() > 0 or has_hidden_annotations:
            return "annotated"
        if self.manual_annotation_page.image_review_status() == "reviewed_no_defect":
            return "reviewed_no_defect"
        return "unreviewed"
