from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.icons import icon
from src.pages.assisted_review_page import AssistedReviewPage
from src.pages.dataset_export_page import DatasetExportPage
from src.pages.manual_annotation_page import ManualAnnotationPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SEM Microcrack Studio")
        self.setMinimumSize(1200, 750)
        self.setWindowIcon(icon("app", active=True))

        self.page_meta = [
            ("Assisted Review", "Model-assisted defect review and operator validation"),
            ("Manual Annotation", "Precise correction tools for SEM microcrack labels"),
            ("Dataset & Export", "Dataset status, quality checks, and export placeholders"),
        ]
        self.nav_buttons: list[QPushButton] = []

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_workspace(), 1)
        self.setCentralWidget(root)

        self._build_status_bar()
        self.switch_page(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(8)

        brand_icon = QLabel()
        brand_icon.setPixmap(icon("app", active=True).pixmap(26, 26))
        brand_title = QLabel("SEM Studio")
        brand_title.setObjectName("sidebarBrand")
        brand_subtitle = QLabel("Microcrack review")
        brand_subtitle.setObjectName("sidebarSubtitle")

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(brand_icon)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand_row.addLayout(brand_text)
        layout.addLayout(brand_row)
        layout.addSpacing(12)

        nav_items = [
            ("Assisted Review", "assisted"),
            ("Manual Annotation", "manual"),
            ("Dataset", "export"),
        ]
        for index, (label, icon_name) in enumerate(nav_items):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setIcon(icon(icon_name))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=index: self.switch_page(page))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        footer = QLabel("Milestone 1 UI shell")
        footer.setObjectName("sidebarFooter")
        layout.addWidget(footer)
        return sidebar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("topHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(14)

        title_column = QVBoxLayout()
        title_column.setSpacing(3)

        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("pageSubtitle")

        title_column.addWidget(self.page_title)
        title_column.addWidget(self.page_subtitle)
        header_layout.addLayout(title_column)
        header_layout.addStretch(1)

        layout.addWidget(header)

        self.stack = QStackedWidget()
        self.stack.addWidget(AssistedReviewPage())
        self.stack.addWidget(ManualAnnotationPage())
        self.stack.addWidget(DatasetExportPage())
        layout.addWidget(self.stack, 1)

        return workspace

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.setObjectName("statusBar")
        self.ready_label = QLabel("Ready")
        self.current_page_label = QLabel()
        status.addWidget(self.ready_label)
        status.addPermanentWidget(self.current_page_label)
        self.setStatusBar(status)

    def switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page_name, subtitle = self.page_meta[index]
        self.page_title.setText(page_name)
        self.page_subtitle.setText(subtitle)
        self.current_page_label.setText(page_name)

        icon_names = ["assisted", "manual", "export"]
        for button_index, button in enumerate(self.nav_buttons):
            active = button_index == index
            button.setProperty("active", active)
            button.setIcon(icon(icon_names[button_index], active=active))
            button.style().unpolish(button)
            button.style().polish(button)
