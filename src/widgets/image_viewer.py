from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QSize
from PySide6.QtGui import QBrush, QColor, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)


RECT_MIN_SIZE = 3.0


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
        self._scene.selectionChanged.connect(self._update_annotation_styles)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._placeholder_text = placeholder_text
        self._placeholder_item: QGraphicsTextItem | None = None
        self._tool_mode = "select"
        self._annotations: list[QGraphicsRectItem] = []
        self._draft_rect_item: QGraphicsRectItem | None = None
        self._draft_origin: QPointF | None = None
        self._annotation_enabled = False
        self._show_placeholder()

    def load_image(self, image_path: str) -> QSize:
        reader = QImageReader(image_path)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            message = reader.errorString() or f"Could not load {Path(image_path).name}"
            raise ValueError(message)

        pixmap = QPixmap.fromImage(image)
        self._annotations.clear()
        self._draft_rect_item = None
        self._draft_origin = None
        self._scene.clear()
        self._placeholder_item = None
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._pixmap_item.setZValue(0)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fit_to_view()
        return image.size()

    def clear(self) -> None:
        self._annotations.clear()
        self._draft_rect_item = None
        self._draft_origin = None
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

    def set_annotation_enabled(self, enabled: bool) -> None:
        self._annotation_enabled = enabled
        self.set_tool_mode(self._tool_mode)

    def set_tool_mode(self, mode: str) -> None:
        if mode not in {"select", "rectangle"}:
            mode = "select"

        self._tool_mode = mode
        if self._annotation_enabled and mode == "rectangle":
            self.setCursor(Qt.CrossCursor)
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            self.unsetCursor()
            self.setDragMode(QGraphicsView.NoDrag)

    def clear_annotations(self) -> None:
        for item in list(self._annotations):
            self._scene.removeItem(item)

        self._annotations.clear()
        self._draft_rect_item = None
        self._draft_origin = None

    def delete_selected_annotation(self) -> None:
        for item in list(self._scene.selectedItems()):
            if item in self._annotations:
                self._scene.removeItem(item)
                self._annotations.remove(item)

    def clear_selection(self) -> None:
        self._scene.clearSelection()

    def get_rect_annotations(self) -> list[dict[str, float]]:
        annotations: list[dict[str, float]] = []
        for item in self._annotations:
            rect = item.rect().normalized()
            annotations.append(
                {
                    "x": rect.x(),
                    "y": rect.y(),
                    "width": rect.width(),
                    "height": rect.height(),
                }
            )

        return annotations

    def mousePressEvent(self, event) -> None:
        if self._can_draw_rectangle(event):
            scene_pos = self._clamp_to_image(self.mapToScene(event.position().toPoint()))
            self._scene.clearSelection()
            self._draft_origin = scene_pos
            self._draft_rect_item = self._make_rect_item(QRectF(scene_pos, scene_pos), preview=True)
            self._scene.addItem(self._draft_rect_item)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._draft_rect_item and self._draft_origin:
            scene_pos = self._clamp_to_image(self.mapToScene(event.position().toPoint()))
            self._draft_rect_item.setRect(QRectF(self._draft_origin, scene_pos).normalized())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._draft_rect_item and self._draft_origin:
            final_rect = self._draft_rect_item.rect().normalized()
            if final_rect.width() < RECT_MIN_SIZE or final_rect.height() < RECT_MIN_SIZE:
                self._scene.removeItem(self._draft_rect_item)
            else:
                self._draft_rect_item.setPen(self._annotation_pen(selected=False))
                self._draft_rect_item.setBrush(self._annotation_brush(selected=False))
                self._draft_rect_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                self._annotations.append(self._draft_rect_item)
                self._draft_rect_item.setSelected(True)
                self._update_annotation_styles()

            self._draft_rect_item = None
            self._draft_origin = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fit_to_view()
        self._center_placeholder()

    def _can_draw_rectangle(self, event) -> bool:
        if not self._annotation_enabled or self._tool_mode != "rectangle" or not self.has_image():
            return False

        if event.button() != Qt.LeftButton:
            return False

        scene_pos = self.mapToScene(event.position().toPoint())
        return self._image_rect().contains(scene_pos)

    def _make_rect_item(self, rect: QRectF, preview: bool = False) -> QGraphicsRectItem:
        item = QGraphicsRectItem(rect)
        item.setZValue(10)
        item.setPen(self._annotation_pen(selected=False))
        item.setBrush(self._annotation_brush(selected=False))
        if not preview:
            item.setFlag(QGraphicsItem.ItemIsSelectable, True)

        return item

    def _annotation_pen(self, selected: bool) -> QPen:
        color = QColor("#facc15") if selected else QColor("#22d3ee")
        pen = QPen(color, 2.0 if selected else 1.6)
        pen.setCosmetic(True)
        return pen

    def _annotation_brush(self, selected: bool) -> QBrush:
        color = QColor(250, 204, 21, 46) if selected else QColor(34, 211, 238, 42)
        return QBrush(color)

    def _update_annotation_styles(self) -> None:
        for item in self._annotations:
            selected = item.isSelected()
            item.setPen(self._annotation_pen(selected=selected))
            item.setBrush(self._annotation_brush(selected=selected))

    def _image_rect(self) -> QRectF:
        if not self._pixmap_item:
            return QRectF()

        return self._pixmap_item.boundingRect()

    def _clamp_to_image(self, point: QPointF) -> QPointF:
        rect = self._image_rect()
        x = min(max(point.x(), rect.left()), rect.right())
        y = min(max(point.y(), rect.top()), rect.bottom())
        return QPointF(x, y)

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
