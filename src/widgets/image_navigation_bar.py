from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from src.icons import icon


class ImageNavigationBar(QFrame):
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("imageNavigationBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        controls = QWidget()
        controls.setObjectName("imageNavigationControls")
        controls.setMaximumWidth(560)

        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(10, 6, 10, 6)
        controls_layout.setSpacing(12)

        self.previous_button = QPushButton("Previous")
        self.previous_button.setObjectName("imageNavigationButton")
        self.previous_button.setIcon(icon("previous"))
        self.previous_button.clicked.connect(self.previous_requested.emit)

        self.info_label = QLabel("No image loaded | 0 / 0")
        self.info_label.setObjectName("imageNavigationLabel")

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("imageNavigationButton")
        self.next_button.setIcon(icon("next"))
        self.next_button.clicked.connect(self.next_requested.emit)

        controls_layout.addWidget(self.previous_button)
        controls_layout.addWidget(self.info_label)
        controls_layout.addWidget(self.next_button)

        layout.addStretch(1)
        layout.addWidget(controls)
        layout.addStretch(1)
        self.set_state("No image loaded", 0, 0, False, False)

    def set_state(
        self,
        filename: str,
        current_index: int,
        total_count: int,
        can_go_previous: bool,
        can_go_next: bool,
    ) -> None:
        if total_count > 0 and current_index > 0:
            label = f"{filename} | {current_index} / {total_count}"
        else:
            label = "No image loaded | 0 / 0"

        self.info_label.setText(label)
        self.previous_button.setEnabled(can_go_previous)
        self.next_button.setEnabled(can_go_next)
