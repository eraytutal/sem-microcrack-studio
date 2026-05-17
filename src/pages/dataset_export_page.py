from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.icons import icon


class DatasetExportPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addLayout(self._build_summary_cards())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_quality_panel(), 1)
        content.addWidget(self._build_export_panel(), 1)
        layout.addLayout(content, 1)

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(14)
        cards = [
            ("Total Images", "0"),
            ("Annotated Images", "0"),
            ("Pending Reviews", "0"),
            ("Accepted Predictions", "0"),
        ]
        for index, (label, value) in enumerate(cards):
            grid.addWidget(self._summary_card(label, value), 0, index)
        return grid

    def _summary_card(self, label: str, value: str) -> QWidget:
        card = QFrame()
        card.setObjectName("summaryCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        value_label = QLabel(value)
        value_label.setObjectName("summaryValue")
        title_label = QLabel(label)
        title_label.setObjectName("summaryLabel")
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        return card

    def _build_quality_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("contentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Quality Checks")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        checks = [
            "Images without annotation",
            "Missing metadata",
            "Pending model suggestions",
            "Uncertain annotations",
        ]
        for check in checks:
            layout.addWidget(self._check_row(check))

        layout.addStretch(1)
        return panel

    def _check_row(self, text: str) -> QWidget:
        row = QFrame()
        row.setObjectName("checkRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        label = QLabel(text)
        count = QLabel("0")
        count.setObjectName("statusPill")
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(count)
        return row

    def _build_export_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("contentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Export")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        buttons = [
            ("Export YOLO Segmentation", "export"),
            ("Export COCO", "export"),
            ("Export JSON Backup", "save"),
            ("Generate Report", "report"),
        ]
        for text, icon_name in buttons:
            button = QPushButton(text)
            button.setObjectName("disabledExportButton")
            button.setIcon(icon(icon_name))
            button.setEnabled(False)
            layout.addWidget(button)

        layout.addStretch(1)

        note = QLabel("Export tools are intentionally disabled in Milestone 1.")
        note.setObjectName("placeholderNote")
        note.setAlignment(Qt.AlignLeft)
        note.setWordWrap(True)
        layout.addWidget(note)
        return panel
