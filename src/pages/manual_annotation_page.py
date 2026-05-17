from __future__ import annotations

from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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

    def __init__(self) -> None:
        super().__init__()

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
            ("Delete", "delete"),
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
            elif text == "Delete":
                button.clicked.connect(self.delete_selected_annotation)
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

        title = QLabel("Annotation Properties")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        label_combo = QComboBox()
        label_combo.setObjectName("propertyField")
        label_combo.addItems(["crack", "scratch", "pit", "void", "uncertain", "no_defect"])
        source_combo = QComboBox()
        source_combo.setObjectName("propertyField")
        source_combo.addItems(["manual", "model"])
        confidence = QDoubleSpinBox()
        confidence.setObjectName("propertyField")
        confidence.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        confidence.setRange(0.0, 1.0)
        confidence.setSingleStep(0.05)
        confidence.setValue(1.0)
        confidence.setDecimals(2)
        exportable = QCheckBox("Exportable to mask")
        exportable.setChecked(True)
        notes = QTextEdit()
        notes.setPlaceholderText("Notes")
        notes.setFixedHeight(120)

        form.addRow("Label", label_combo)
        form.addRow("Source", source_combo)
        form.addRow("Confidence", confidence)
        form.addRow("", exportable)
        form.addRow("Notes", notes)
        layout.addLayout(form)
        layout.addStretch(1)

        save = QPushButton("Save Annotation")
        save.setIcon(icon("save", active=True))
        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setIcon(icon("delete"))
        self.clear_selection_button.clicked.connect(self.clear_selection)
        layout.addWidget(save)
        layout.addWidget(self.clear_selection_button)
        self.set_tool_mode("select")
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

    def set_navigation_state(
        self,
        filename: str,
        current_index: int,
        total_count: int,
        can_go_previous: bool,
        can_go_next: bool,
    ) -> None:
        self.navigation_bar.set_state(filename, current_index, total_count, can_go_previous, can_go_next)
