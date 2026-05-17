from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


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
        self.current_folder_path: str | None = None
        self.image_paths: list[str] = []
        self.current_image_index: int = -1
        self.current_image_path: str | None = None
        self.current_image_size: tuple[int, int] | None = None

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
        self.assisted_review_page = AssistedReviewPage()
        self.manual_annotation_page = ManualAnnotationPage()
        self.dataset_export_page = DatasetExportPage()
        self.assisted_review_page.open_image_requested.connect(self.open_image)
        self.assisted_review_page.open_folder_requested.connect(self.open_image_folder)
        self.assisted_review_page.image_index_selected.connect(self.load_image_at_index)
        self.assisted_review_page.previous_image_requested.connect(self.load_previous_image)
        self.assisted_review_page.next_image_requested.connect(self.load_next_image)
        self.stack.addWidget(self.assisted_review_page)
        self.stack.addWidget(self.manual_annotation_page)
        self.stack.addWidget(self.dataset_export_page)
        layout.addWidget(self.stack, 1)

        return workspace

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.setObjectName("statusBar")
        self.ready_label = QLabel("Ready")
        self.image_status_label = QLabel("")
        self.current_page_label = QLabel()
        status.addWidget(self.ready_label)
        status.addWidget(self.image_status_label, 1)
        status.addPermanentWidget(self.current_page_label)
        self.setStatusBar(status)

    def open_image(self) -> None:
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SEM Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)",
        )
        if not image_path:
            return

        self.current_folder_path = str(Path(image_path).parent)
        self.image_paths = [image_path]
        self.current_image_index = 0
        self.assisted_review_page.set_image_list(self.image_paths, self.current_image_index)
        self.load_image(image_path)

    def open_image_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "Open SEM Image Folder")
        if not folder_path:
            return

        image_paths = self._collect_image_paths(folder_path)
        if not image_paths:
            QMessageBox.warning(
                self,
                "No Images Found",
                "No supported SEM image files were found in the selected folder.",
            )
            return

        self.current_folder_path = folder_path
        self.image_paths = image_paths
        self.current_image_index = 0
        self.assisted_review_page.set_image_list(self.image_paths, self.current_image_index)
        self.load_image_at_index(self.current_image_index)

    def open_folder(self) -> None:
        self.open_image_folder()

    def load_image(self, image_path: str) -> None:
        try:
            image_size = self.assisted_review_page.image_viewer.load_image(image_path)
            self.manual_annotation_page.image_viewer.load_image(image_path)
        except ValueError as error:
            QMessageBox.critical(self, "Image Loading Failed", str(error))
            return

        self.current_image_path = image_path
        self.current_image_size = (image_size.width(), image_size.height())
        if image_path in self.image_paths:
            self.current_image_index = self.image_paths.index(image_path)
            self.assisted_review_page.set_current_image_index(self.current_image_index)
        self.update_navigation_state()
        self._update_status_bar()

    def load_image_at_index(self, index: int) -> None:
        if not 0 <= index < len(self.image_paths):
            return

        self.current_image_index = index
        self.load_image(self.image_paths[index])

    def load_previous_image(self) -> None:
        if not self.image_paths:
            return

        next_index = max(0, self.current_image_index - 1)
        self.load_image_at_index(next_index)

    def load_next_image(self) -> None:
        if not self.image_paths:
            return

        next_index = min(len(self.image_paths) - 1, self.current_image_index + 1)
        self.load_image_at_index(next_index)

    def update_navigation_state(self) -> None:
        self.assisted_review_page.update_navigation_state(self.current_image_index)

    def switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page_name, subtitle = self.page_meta[index]
        self.page_title.setText(page_name)
        self.page_subtitle.setText(subtitle)
        self._update_status_bar(page_name)

        icon_names = ["assisted", "manual", "export"]
        for button_index, button in enumerate(self.nav_buttons):
            active = button_index == index
            button.setProperty("active", active)
            button.setIcon(icon(icon_names[button_index], active=active))
            button.style().unpolish(button)
            button.style().polish(button)

    def _update_status_bar(self, page_name: str | None = None) -> None:
        if page_name is None:
            page_name = self.page_meta[self.stack.currentIndex()][0]

        if self.current_image_path and self.current_image_size:
            filename = Path(self.current_image_path).name
            width, height = self.current_image_size
            index_text = self._image_index_status()
            self.image_status_label.setText(f"{filename} | {width} x {height} | {index_text}")
        else:
            self.image_status_label.setText("No image loaded")

        self.current_page_label.setText(page_name)

    def _image_index_status(self) -> str:
        if self.image_paths and self.current_image_index >= 0:
            return f"{self.current_image_index + 1} / {len(self.image_paths)}"

        return "1 / 1"

    def _collect_image_paths(self, folder_path: str) -> list[str]:
        folder = Path(folder_path)
        return [
            str(path)
            for path in sorted(folder.iterdir(), key=lambda item: item.name.lower())
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]
