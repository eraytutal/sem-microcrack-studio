from __future__ import annotations

from PySide6.QtCore import QLocale, Qt
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
from src.widgets.image_viewer import ImageViewer


class ManualAnnotationPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_tool_row())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_viewer(), 1)
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
        for text, icon_name in tools:
            button = QToolButton()
            button.setObjectName("toolIconButton")
            button.setText(text)
            button.setToolTip(text)
            button.setIcon(icon(icon_name))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            layout.addWidget(button)

        layout.addStretch(1)
        return row

    def _build_viewer(self) -> QWidget:
        self.image_viewer = ImageViewer("Manual annotation canvas")
        return self.image_viewer

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
        clear = QPushButton("Clear Selection")
        clear.setIcon(icon("delete"))
        layout.addWidget(save)
        layout.addWidget(clear)
        return panel
