from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon
from src.widgets.image_viewer import ImageViewer


class AssistedReviewPage(QWidget):
    open_image_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_action_row())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_viewer(), 1)
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
