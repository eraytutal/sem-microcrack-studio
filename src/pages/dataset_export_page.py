from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon


class DatasetExportPage(QWidget):
    refresh_requested = Signal()
    browse_yolo_output_requested = Signal()
    export_yolo_requested = Signal(dict)

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

        output_label = QLabel("Output Folder")
        output_label.setObjectName("fieldLabel")
        self.yolo_output_field = QLineEdit("data/exports/yolo_seg")
        self.yolo_output_field.setObjectName("propertyField")
        browse_button = QPushButton("Browse")
        browse_button.setIcon(icon("open_folder"))
        browse_button.clicked.connect(self.browse_yolo_output_requested.emit)
        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        output_row.addWidget(self.yolo_output_field, 1)
        output_row.addWidget(browse_button)
        layout.addWidget(output_label)
        layout.addLayout(output_row)

        split_grid = QGridLayout()
        split_grid.setHorizontalSpacing(8)
        split_grid.setVerticalSpacing(8)
        self.train_spin = self._percent_spinbox(70)
        self.val_spin = self._percent_spinbox(20)
        self.test_spin = self._percent_spinbox(10)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        self.seed_spin.setObjectName("propertyField")
        for column, (label_text, widget) in enumerate(
            [
                ("Train %", self.train_spin),
                ("Val %", self.val_spin),
                ("Test %", self.test_spin),
                ("Seed", self.seed_spin),
            ]
        ):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            split_grid.addWidget(label, 0, column)
            split_grid.addWidget(widget, 1, column)
        layout.addLayout(split_grid)

        self.include_no_defect_checkbox = QCheckBox("Include No Defect images")
        self.include_no_defect_checkbox.setChecked(True)
        self.include_uncertain_checkbox = QCheckBox("Include uncertain class")
        self.include_uncertain_checkbox.setChecked(False)
        layout.addWidget(self.include_no_defect_checkbox)
        layout.addWidget(self.include_uncertain_checkbox)

        self.export_yolo_button = QPushButton("Export YOLO-Seg Dataset")
        self.export_yolo_button.setIcon(icon("export", active=True))
        self.export_yolo_button.setProperty("emphasized", True)
        self.export_yolo_button.clicked.connect(lambda: self.export_yolo_requested.emit(self.yolo_export_settings()))
        layout.addWidget(self.export_yolo_button)

        note = QLabel("Exports confirmed annotations only. Predictions are ignored unless accepted and saved.")
        note.setObjectName("placeholderNote")
        note.setAlignment(Qt.AlignLeft)
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return panel

    def set_yolo_output_dir(self, output_dir: str) -> None:
        self.yolo_output_field.setText(output_dir)

    def yolo_export_settings(self) -> dict[str, object]:
        return {
            "output_dir": self.yolo_output_field.text().strip(),
            "train_percent": self.train_spin.value(),
            "val_percent": self.val_spin.value(),
            "test_percent": self.test_spin.value(),
            "seed": self.seed_spin.value(),
            "include_no_defect": self.include_no_defect_checkbox.isChecked(),
            "include_uncertain": self.include_uncertain_checkbox.isChecked(),
        }

    def _percent_spinbox(self, value: int) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(0, 100)
        spinbox.setValue(value)
        spinbox.setObjectName("propertyField")
        return spinbox
