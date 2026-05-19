from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon
from src.widgets.image_navigation_bar import ImageNavigationBar
from src.widgets.image_viewer import ImageViewer


class AssistedReviewPage(QWidget):
    open_image_requested = Signal()
    open_folder_requested = Signal()
    previous_image_requested = Signal()
    next_image_requested = Signal()
    run_detection_requested = Signal()
    accept_prediction_requested = Signal()
    reject_prediction_requested = Signal()
    prediction_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_action_row())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_viewer_column(), 1)
        content.addWidget(self._build_suggestions_panel())
        layout.addLayout(content, 1)

    def _build_action_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("toolbarPanel")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        actions = [
            ("Open Image", "open_image"),
            ("Open Folder", "open_folder"),
            ("Run Detection", "detect"),
            ("Save Review", "save"),
        ]
        for text, icon_name in actions:
            button = QPushButton(text)
            button.setIcon(icon(icon_name))
            if text == "Open Image":
                button.clicked.connect(self.open_image_requested.emit)
            elif text == "Open Folder":
                button.clicked.connect(self.open_folder_requested.emit)
            elif text == "Run Detection":
                button.clicked.connect(self.run_detection_requested.emit)
            layout.addWidget(button)

        layout.addStretch(1)

        label = QLabel("Confidence Threshold")
        label.setObjectName("fieldLabel")
        value = QLabel("0.25")
        value.setObjectName("thresholdValue")
        slider = QSlider(Qt.Horizontal)
        slider.setObjectName("thresholdSlider")
        slider.setRange(0, 100)
        slider.setValue(25)
        slider.setFixedWidth(150)
        slider.setEnabled(False)

        layout.addWidget(label)
        layout.addWidget(slider)
        layout.addWidget(value)
        return row

    def _build_viewer_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.image_viewer = ImageViewer("Load an SEM image to start assisted review")
        self.image_viewer.selected_annotation_changed.connect(self._handle_overlay_selection_changed)
        self.navigation_bar = ImageNavigationBar()
        self.navigation_bar.previous_requested.connect(self.previous_image_requested.emit)
        self.navigation_bar.next_requested.connect(self.next_image_requested.emit)
        layout.addWidget(self.image_viewer, 1)
        layout.addWidget(self.navigation_bar)
        return column

    def _build_suggestions_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        panel.setFixedWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Model Suggestions")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.suggestion_list = QListWidget()
        self.suggestion_list.setObjectName("annotationList")
        self.suggestion_list.currentItemChanged.connect(self._handle_suggestion_selection)
        self.empty_suggestions_label = QLabel("No model suggestions.")
        self.empty_suggestions_label.setObjectName("mutedText")
        self.empty_suggestions_label.setAlignment(Qt.AlignCenter)
        self.empty_suggestions_label.setWordWrap(True)
        layout.addWidget(self.suggestion_list)
        layout.addWidget(self.empty_suggestions_label)

        layout.addStretch(1)

        self.accept_button = QPushButton("Accept")
        self.accept_button.setIcon(icon("accept", active=True))
        self.accept_button.clicked.connect(self.accept_prediction_requested.emit)
        self.reject_button = QPushButton("Reject")
        self.reject_button.setIcon(icon("reject"))
        self.reject_button.clicked.connect(self.reject_prediction_requested.emit)
        self.edit_button = QPushButton("Edit in Annotation")
        self.edit_button.setIcon(icon("edit"))
        self.edit_button.clicked.connect(self._show_edit_placeholder)

        layout.addWidget(self.accept_button)
        layout.addWidget(self.reject_button)
        layout.addWidget(self.edit_button)
        self.set_predictions([])
        return panel

    def set_navigation_state(
        self,
        filename: str,
        current_index: int,
        total_count: int,
        can_go_previous: bool,
        can_go_next: bool,
    ) -> None:
        self.navigation_bar.set_state(filename, current_index, total_count, can_go_previous, can_go_next)

    def set_predictions(self, predictions: list[dict[str, object]]) -> None:
        selected_id = self.selected_prediction_id()
        self.suggestion_list.blockSignals(True)
        self.suggestion_list.clear()
        for index, prediction in enumerate(predictions, start=1):
            prediction_id = str(prediction.get("id") or f"pred_{index:03d}")
            label = str(prediction.get("label") or "crack")
            confidence = prediction.get("confidence")
            try:
                confidence_text = f"{float(confidence):.2f}"
            except (TypeError, ValueError):
                confidence_text = "--"
            status = str(prediction.get("status") or "pending")
            item = QListWidgetItem(f"{prediction_id} | {label} | {confidence_text} | {status}")
            item.setData(Qt.UserRole, prediction_id)
            item.setData(Qt.UserRole + 1, status)
            self.suggestion_list.addItem(item)
            if prediction_id == selected_id:
                self.suggestion_list.setCurrentItem(item)

        has_predictions = self.suggestion_list.count() > 0
        self.suggestion_list.setVisible(has_predictions)
        self.empty_suggestions_label.setVisible(not has_predictions)
        self.suggestion_list.blockSignals(False)
        self._update_action_state()

    def selected_prediction_id(self) -> str:
        item = self.suggestion_list.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def select_prediction(self, prediction_id: str) -> None:
        self.suggestion_list.blockSignals(True)
        for row in range(self.suggestion_list.count()):
            item = self.suggestion_list.item(row)
            if str(item.data(Qt.UserRole) or "") == prediction_id:
                self.suggestion_list.setCurrentItem(item)
                break
        self.suggestion_list.blockSignals(False)
        self._update_action_state()

    def _handle_suggestion_selection(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        self._update_action_state()
        if current:
            self.prediction_selected.emit(str(current.data(Qt.UserRole) or ""))

    def _handle_overlay_selection_changed(self, annotation: object) -> None:
        if isinstance(annotation, dict) and annotation.get("item_kind") == "prediction":
            self.select_prediction(str(annotation.get("id") or ""))
        else:
            self._update_action_state()

    def _update_action_state(self) -> None:
        item = self.suggestion_list.currentItem()
        has_selection = item is not None
        is_pending = has_selection and str(item.data(Qt.UserRole + 1) or "pending") == "pending"
        self.accept_button.setEnabled(is_pending)
        self.reject_button.setEnabled(is_pending)
        self.edit_button.setEnabled(has_selection)

    def _show_edit_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "Edit in Annotation",
            "Edit in Annotation will be added later.",
        )
