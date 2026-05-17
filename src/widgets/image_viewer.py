from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView


class ImageViewer(QGraphicsView):
    def __init__(self, placeholder_text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("imageViewer")
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setAlignment(Qt.AlignCenter)
        self.setBackgroundBrush(QColor("#05070a"))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._placeholder_text = placeholder_text
        self._placeholder_item: QGraphicsTextItem | None = None
        self._show_placeholder()

    def load_image(self, image_path: str) -> QSize:
        reader = QImageReader(image_path)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            message = reader.errorString() or f"Could not load {Path(image_path).name}"
            raise ValueError(message)

        pixmap = QPixmap.fromImage(image)
        self._scene.clear()
        self._placeholder_item = None
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fit_to_view()
        return image.size()

    def clear(self) -> None:
        self._pixmap_item = None
        self._scene.clear()
        self._show_placeholder()

    def fit_to_view(self) -> None:
        if not self._pixmap_item:
            return

        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)

    def has_image(self) -> bool:
        return self._pixmap_item is not None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fit_to_view()
        self._center_placeholder()

    def _show_placeholder(self) -> None:
        self._scene.setSceneRect(0, 0, max(self.width(), 640), max(self.height(), 420))
        self._placeholder_item = self._scene.addText(self._placeholder_text)
        font = self._placeholder_item.font()
        font.setPointSize(15)
        font.setBold(True)
        self._placeholder_item.setFont(font)
        self._placeholder_item.setDefaultTextColor(QColor("#6f7f92"))
        self._center_placeholder()

    def _center_placeholder(self) -> None:
        if not self._placeholder_item or self.has_image():
            return

        rect = self.viewport().rect()
        scene_rect = self.mapToScene(rect).boundingRect()
        text_rect = self._placeholder_item.boundingRect()
        x = scene_rect.center().x() - text_rect.width() / 2
        y = scene_rect.center().y() - text_rect.height() / 2
        self._placeholder_item.setPos(x, y)
