from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon


class DatasetExportPage(QWidget):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addLayout(self._build_summary_cards())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_status_panel(), 2)
        content.addWidget(self._build_export_panel(), 1)
        layout.addLayout(content, 1)

    def _build_summary_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(14)
        cards = [
            ("Total Images", "0"),
            ("Annotated Images", "0"),
            ("No Defect Images", "0"),
            ("Unreviewed Images", "0"),
        ]
        self.summary_values: dict[str, QLabel] = {}
        for index, (label, value) in enumerate(cards):
            card, value_label = self._summary_card(label, value)
            self.summary_values[label] = value_label
            grid.addWidget(card, 0, index)
        return grid

    def _summary_card(self, label: str, value: str) -> tuple[QWidget, QLabel]:
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
        return card, value_label

    def _build_status_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("contentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Image Status")
        title.setObjectName("panelTitle")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(icon("fit"))
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.refresh_button)
        layout.addLayout(title_row)

        self.status_table = QTableWidget(0, 3)
        self.status_table.setObjectName("datasetStatusTable")
        self.status_table.setHorizontalHeaderLabels(["Filename", "Status", "Annotation Count"])
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.status_table.setSelectionMode(QTableWidget.SingleSelection)
        self.status_table.setAlternatingRowColors(True)
        self.status_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.status_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.status_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.status_table, 1)

        self.empty_table_note = QLabel("Open a folder to review dataset status.")
        self.empty_table_note.setObjectName("placeholderNote")
        self.empty_table_note.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.empty_table_note)
        return panel

    def update_dataset_status(self, status_data: dict[str, object]) -> None:
        self.summary_values["Total Images"].setText(str(status_data.get("total_images", 0)))
        self.summary_values["Annotated Images"].setText(str(status_data.get("annotated_images", 0)))
        self.summary_values["No Defect Images"].setText(str(status_data.get("no_defect_images", 0)))
        self.summary_values["Unreviewed Images"].setText(str(status_data.get("unreviewed_images", 0)))

        rows = status_data.get("rows", [])
        if not isinstance(rows, list):
            rows = []

        self.status_table.setRowCount(len(rows))
        for row_index, row_data in enumerate(rows):
            if not isinstance(row_data, dict):
                continue

            filename = str(row_data.get("filename", ""))
            status = str(row_data.get("status", "Unreviewed"))
            annotation_count = str(row_data.get("annotation_count", 0))

            filename_item = QTableWidgetItem(filename)
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setData(Qt.UserRole, status.lower().replace(" ", "_"))
            status_item.setForeground(
                QColor(
                    {
                        "Annotated": "#88e5f7",
                        "No Defect": "#86efac",
                        "Unreviewed": "#cbd5e1",
                    }.get(status, "#cbd5e1")
                )
            )
            count_item = QTableWidgetItem(annotation_count)
            count_item.setTextAlignment(Qt.AlignCenter)

            self.status_table.setItem(row_index, 0, filename_item)
            self.status_table.setItem(row_index, 1, status_item)
            self.status_table.setItem(row_index, 2, count_item)

        self.empty_table_note.setVisible(len(rows) == 0)

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
