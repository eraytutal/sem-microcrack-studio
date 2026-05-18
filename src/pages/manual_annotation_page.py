from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon
from src.widgets.image_navigation_bar import ImageNavigationBar
from src.widgets.image_viewer import ImageViewer


class ManualAnnotationPage(QWidget):
    previous_image_requested = Signal()
    next_image_requested = Signal()
    save_annotation_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._loading_properties = False
        self._selected_annotation: dict[str, object] | None = None
        self._panel_mode = "defaults"
        self._default_properties = {
            "label": "crack",
            "source": "manual",
            "confidence": None,
            "exportable_to_mask": True,
            "status": "pending",
            "notes": "",
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_tool_row())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_viewer_column(), 1)
        content.addWidget(self._build_properties_panel())
        layout.addLayout(content, 1)

    def _build_tool_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("toolbarPanel")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        tools = [
            ("Select", "select"),
            ("Rectangle", "rectangle"),
            ("Polygon", "polygon"),
            ("Undo", "undo"),
            ("Redo", "redo"),
            ("Zoom In", "zoom_in"),
            ("Zoom Out", "zoom_out"),
            ("Fit", "fit"),
        ]
        self.tool_buttons: dict[str, QToolButton] = {}
        for text, icon_name in tools:
            button = QToolButton()
            button.setObjectName("toolIconButton")
            button.setText(text)
            button.setToolTip(text)
            button.setIcon(icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            if text in {"Select", "Rectangle"}:
                button.setCheckable(True)
                button.clicked.connect(lambda checked=False, mode=icon_name: self.set_tool_mode(mode))
                self.tool_buttons[icon_name] = button
            layout.addWidget(button)

        layout.addStretch(1)
        return row

    def _build_viewer_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.image_viewer = ImageViewer("Manual annotation canvas")
        self.image_viewer.set_annotation_enabled(True)
        self.image_viewer.set_tool_mode("select")
        self.image_viewer.selected_annotation_changed.connect(self._handle_selected_annotation_changed)
        self.navigation_bar = ImageNavigationBar()
        self.navigation_bar.previous_requested.connect(self.previous_image_requested.emit)
        self.navigation_bar.next_requested.connect(self.next_image_requested.emit)
        layout.addWidget(self.image_viewer, 1)
        layout.addWidget(self.navigation_bar)
        return column

    def _build_properties_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        panel.setFixedWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.panel_title = QLabel("New Annotation Defaults")
        self.panel_title.setObjectName("panelTitle")
        layout.addWidget(self.panel_title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.label_combo = QComboBox()
        self.label_combo.setObjectName("propertyField")
        self.label_combo.setEditable(False)
        self.label_combo.addItems(["crack", "scratch", "pit", "void", "uncertain", "no_defect"])
        self.label_combo.setCurrentText("crack")
        self.source_field = QLineEdit("manual")
        self.source_field.setObjectName("propertyField")
        self.source_field.setReadOnly(True)
        self.confidence_field = QLineEdit("--")
        self.confidence_field.setObjectName("propertyField")
        self.confidence_field.setReadOnly(True)
        self.exportable_checkbox = QCheckBox("Exportable to mask")
        self.exportable_checkbox.setChecked(True)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notes")
        self.notes_edit.setFixedHeight(120)

        self.label_combo.currentTextChanged.connect(self._handle_property_changed)
        self.exportable_checkbox.stateChanged.connect(self._handle_property_changed)
        self.notes_edit.textChanged.connect(self._handle_property_changed)

        form.addRow("Label", self.label_combo)
        form.addRow("Source", self.source_field)
        form.addRow("Confidence", self.confidence_field)
        form.addRow("", self.exportable_checkbox)
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)
        layout.addStretch(1)

        self.add_annotation_button = QPushButton("Add Annotation")
        self.add_annotation_button.setIcon(icon("accept", active=True))
        self.add_annotation_button.clicked.connect(self.add_pending_annotation)
        self.discard_button = QPushButton("Discard")
        self.discard_button.setIcon(icon("reject"))
        self.discard_button.clicked.connect(self.discard_pending_annotation)
        self.update_annotation_button = QPushButton("Update Annotation")
        self.update_annotation_button.setIcon(icon("edit", active=True))
        self.update_annotation_button.clicked.connect(self.update_selected_annotation)
        self.delete_annotation_button = QPushButton("Delete")
        self.delete_annotation_button.setIcon(icon("delete"))
        self.delete_annotation_button.clicked.connect(self.delete_selected_annotation)
        self.save_all_button = QPushButton("Save All to JSON")
        self.save_all_button.setIcon(icon("save", active=True))
        self.save_all_button.clicked.connect(self.save_annotation_requested.emit)
        layout.addWidget(self.add_annotation_button)
        layout.addWidget(self.discard_button)
        layout.addWidget(self.update_annotation_button)
        layout.addWidget(self.delete_annotation_button)
        layout.addWidget(self.save_all_button)
        self.set_tool_mode("select")
        self._apply_properties_to_panel(self._default_properties)
        self.image_viewer.set_default_annotation_properties(self._default_properties)
        self._set_panel_mode("defaults")
        return panel

    def set_tool_mode(self, mode: str) -> None:
        if mode not in {"select", "rectangle"}:
            mode = "select"

        self.image_viewer.set_tool_mode(mode)
        for button_mode, button in self.tool_buttons.items():
            button.setChecked(button_mode == mode)

    def delete_selected_annotation(self) -> None:
        self.image_viewer.delete_selected_annotation()

    def clear_selection(self) -> None:
        self.image_viewer.clear_selection()

    def add_pending_annotation(self) -> None:
        properties = {**self._panel_properties(), "status": "verified"}
        if self.image_viewer.confirm_selected_annotation(properties):
            self.image_viewer.clear_selection()
            self._update_save_all_state()

    def discard_pending_annotation(self) -> None:
        self.image_viewer.discard_selected_annotation()
        self._update_save_all_state()

    def update_selected_annotation(self) -> None:
        if self._panel_mode != "confirmed":
            return

        self.image_viewer.update_selected_annotation_properties({**self._panel_properties(), "status": "verified"})
        self._update_save_all_state()

    def set_navigation_state(
        self,
        filename: str,
        current_index: int,
        total_count: int,
        can_go_previous: bool,
        can_go_next: bool,
    ) -> None:
        self.navigation_bar.set_state(filename, current_index, total_count, can_go_previous, can_go_next)

    def annotation_save_context(self) -> dict[str, object]:
        return {
            "notes": self.notes_edit.toPlainText(),
        }

    def _handle_selected_annotation_changed(self, annotation: object) -> None:
        self._selected_annotation = annotation if isinstance(annotation, dict) else None
        if self._selected_annotation:
            self._apply_properties_to_panel(self._selected_annotation)
            if self._selected_annotation.get("status") == "pending":
                self._set_panel_mode("pending")
            else:
                self._set_panel_mode("confirmed")
        else:
            self._apply_properties_to_panel(self._default_properties)
            self._set_panel_mode("defaults")

    def _handle_property_changed(self, *args) -> None:
        if self._loading_properties:
            return

        properties = self._panel_properties()
        if self._selected_annotation:
            if self._panel_mode == "pending":
                self.image_viewer.update_selected_annotation_properties({**properties, "status": "pending"})
                self._selected_annotation = self.image_viewer.get_selected_annotation()
        else:
            properties["source"] = "manual"
            properties["status"] = "pending"
            self._default_properties.update(properties)
            self.image_viewer.set_default_annotation_properties(self._default_properties)
            self.source_field.setText("manual")

    def _panel_properties(self) -> dict[str, object]:
        return {
            "label": self.label_combo.currentText(),
            "source": "manual",
            "confidence": None,
            "exportable_to_mask": self.exportable_checkbox.isChecked(),
            "status": "pending" if self._panel_mode != "confirmed" else "verified",
            "notes": self.notes_edit.toPlainText(),
        }

    def _apply_properties_to_panel(self, properties: dict[str, object]) -> None:
        self._loading_properties = True
        label = str(properties.get("label") or self._default_properties["label"])
        label_index = self.label_combo.findText(label)
        self.label_combo.setCurrentIndex(max(label_index, 0))
        self.source_field.setText("manual")
        self.confidence_field.setText("--")
        self.exportable_checkbox.setChecked(bool(properties.get("exportable_to_mask", True)))
        self.notes_edit.setPlainText(str(properties.get("notes") or ""))
        self._loading_properties = False

    def _set_panel_mode(self, mode: str) -> None:
        self._panel_mode = mode
        self.panel_title.setText(
            {
                "defaults": "New Annotation Defaults",
                "pending": "Review New Annotation",
                "confirmed": "Selected Annotation",
            }.get(mode, "New Annotation Defaults")
        )
        self.add_annotation_button.setVisible(mode == "pending")
        self.discard_button.setVisible(mode == "pending")
        self.update_annotation_button.setVisible(mode == "confirmed")
        self.delete_annotation_button.setVisible(mode == "confirmed")
        self._update_save_all_state()

    def _update_save_all_state(self) -> None:
        self.save_all_button.setEnabled(
            self.image_viewer.confirmed_annotation_count() > 0
            and not self.image_viewer.has_pending_annotation()
        )
