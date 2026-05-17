from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon
from src.widgets.image_viewer import ImageViewer


class AssistedReviewPage(QWidget):
    open_image_requested = Signal()
    open_folder_requested = Signal()
    image_index_selected = Signal(int)
    previous_image_requested = Signal()
    next_image_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._updating_image_list = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_action_row())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_viewer(), 1)
        content.addWidget(self._build_suggestions_panel())
        layout.addLayout(content, 1)
        self.set_image_list([])

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

    def _build_viewer(self) -> QWidget:
        self.image_viewer = ImageViewer("Load an SEM image to start assisted review")
        return self.image_viewer

    def _build_suggestions_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        panel.setFixedWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        image_list_title = QLabel("Image List")
        image_list_title.setObjectName("panelTitle")
        layout.addWidget(image_list_title)

        nav_row = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.previous_button.setIcon(icon("previous"))
        self.previous_button.clicked.connect(self.previous_image_requested.emit)
        self.next_button = QPushButton("Next")
        self.next_button.setIcon(icon("next"))
        self.next_button.clicked.connect(self.next_image_requested.emit)
        nav_row.addWidget(self.previous_button)
        nav_row.addWidget(self.next_button)
        layout.addLayout(nav_row)

        self.image_list = QListWidget()
        self.image_list.setObjectName("imageList")
        self.image_list.currentRowChanged.connect(self._handle_image_row_changed)
        layout.addWidget(self.image_list, 1)

        title = QLabel("Model Suggestions")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        predictions = [
            ("Possible crack", "0.82", "pending"),
            ("Possible scratch", "0.61", "pending"),
            ("Uncertain region", "0.44", "pending"),
        ]
        for name, confidence, state in predictions:
            layout.addWidget(self._prediction_row(name, confidence, state))

        layout.addStretch(1)

        accept = QPushButton("Accept")
        accept.setIcon(icon("accept", active=True))
        reject = QPushButton("Reject")
        reject.setIcon(icon("reject"))
        edit = QPushButton("Edit in Annotation")
        edit.setIcon(icon("edit"))

        layout.addWidget(accept)
        layout.addWidget(reject)
        layout.addWidget(edit)
        return panel

    def set_image_list(self, image_paths: list[str], current_index: int = -1) -> None:
        self._updating_image_list = True
        self.image_list.clear()
        for image_path in image_paths:
            item = QListWidgetItem(image_path)
            item.setText(image_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1])
            item.setToolTip(image_path)
            self.image_list.addItem(item)

        if 0 <= current_index < self.image_list.count():
            self.image_list.setCurrentRow(current_index)

        has_any = self.image_list.count() > 0
        self.image_list.setEnabled(has_any)
        self.update_navigation_state(current_index)
        self._updating_image_list = False

    def set_current_image_index(self, index: int) -> None:
        if not 0 <= index < self.image_list.count():
            return

        self._updating_image_list = True
        self.image_list.setCurrentRow(index)
        self.update_navigation_state(index)
        self._updating_image_list = False

    def update_navigation_state(self, current_index: int) -> None:
        total = self.image_list.count()
        self.previous_button.setEnabled(total > 1 and current_index > 0)
        self.next_button.setEnabled(total > 1 and 0 <= current_index < total - 1)

    def _handle_image_row_changed(self, row: int) -> None:
        if self._updating_image_list or row < 0:
            return

        self.image_index_selected.emit(row)

    def _prediction_row(self, name: str, confidence: str, state: str) -> QWidget:
        row = QFrame()
        row.setObjectName("predictionRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        top = QHBoxLayout()
        title = QLabel(name)
        title.setObjectName("predictionTitle")
        status = QLabel(state)
        status.setObjectName("statusPill")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(status)

        confidence_label = QLabel(f"confidence {confidence}")
        confidence_label.setObjectName("mutedText")

        layout.addLayout(top)
        layout.addWidget(confidence_label)
        return row
