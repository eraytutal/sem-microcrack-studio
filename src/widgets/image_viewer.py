from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QSize, Signal
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
ANNOTATION_DATA_ROLE = 0
DEFAULT_ANNOTATION_PROPERTIES = {
    "label": "crack",
    "source": "manual",
    "confidence": None,
    "exportable_to_mask": True,
    "status": "pending",
    "notes": "",
}


class ImageViewer(QGraphicsView):
    selected_annotation_changed = Signal(object)
    drawing_blocked = Signal(str)

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
        self._scene.selectionChanged.connect(self._handle_selection_changed)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._placeholder_text = placeholder_text
        self._placeholder_item: QGraphicsTextItem | None = None
        self._tool_mode = "select"
        self._annotations: list[QGraphicsRectItem] = []
        self._draft_rect_item: QGraphicsRectItem | None = None
        self._draft_origin: QPointF | None = None
        self._annotation_enabled = False
        self._default_annotation_properties = dict(DEFAULT_ANNOTATION_PROPERTIES)
        self._selection_update_in_progress = False
        self._drawing_blocked_reason: str | None = None
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
        self.selected_annotation_changed.emit(None)

    def delete_selected_annotation(self) -> None:
        selected = self._selected_annotation_item()
        if selected:
            self._scene.removeItem(selected)
            self._annotations.remove(selected)
            self.selected_annotation_changed.emit(None)

    def clear_selection(self) -> None:
        self._scene.clearSelection()

    def confirmed_annotation_count(self) -> int:
        return sum(1 for item in self._annotations if self._is_confirmed(item))

    def has_pending_annotation(self) -> bool:
        return any(self._is_pending(item) for item in self._annotations)

    def get_confirmed_annotations(self) -> list[dict[str, Any]]:
        annotations: list[dict[str, Any]] = []
        confirmed_items = [item for item in self._annotations if self._is_confirmed(item)]
        for index, item in enumerate(confirmed_items, start=1):
            annotations.append(
                {
                    **self._annotation_snapshot(item),
                    "display_id": f"ann_{index:03d}",
                    "annotation_item_id": self._annotation_item_id(item),
                }
            )

        return annotations

    def select_annotation_by_id(self, annotation_item_id: str) -> bool:
        for item in self._annotations:
            if self._annotation_item_id(item) == annotation_item_id and self._is_confirmed(item):
                self._scene.clearSelection()
                item.setSelected(True)
                self.centerOn(item)
                return True

        return False

    def set_default_annotation_properties(self, properties: dict[str, Any]) -> None:
        self._default_annotation_properties.update(self._normalize_annotation_properties(properties))

    def set_drawing_blocked(self, reason: str | None) -> None:
        self._drawing_blocked_reason = reason

    def get_selected_annotation(self) -> dict[str, Any] | None:
        selected = self._selected_annotation_item()
        if not selected:
            return None

        return self._annotation_snapshot(selected)

    def update_selected_annotation_properties(self, properties: dict[str, Any]) -> None:
        selected = self._selected_annotation_item()
        if not selected:
            return

        selected.setData(
            ANNOTATION_DATA_ROLE,
            {
                **self._item_properties(selected),
                **self._normalize_annotation_properties(properties),
            },
        )
        self._update_badge(selected)
        self.selected_annotation_changed.emit(self._annotation_snapshot(selected))

    def confirm_selected_annotation(self, properties: dict[str, Any]) -> bool:
        selected = self._selected_annotation_item()
        if not selected or not self._is_pending(selected):
            return False

        self.update_selected_annotation_properties({**properties, "status": "verified"})
        selected.setSelected(False)
        self._update_annotation_styles()
        return True

    def discard_selected_annotation(self) -> None:
        selected = self._selected_annotation_item()
        if selected and self._is_pending(selected):
            self._scene.removeItem(selected)
            self._annotations.remove(selected)
            self.selected_annotation_changed.emit(None)

    def get_rect_annotations(self) -> list[dict[str, Any]]:
        annotations: list[dict[str, Any]] = []
        for item in self._annotations:
            if self._is_confirmed(item):
                annotations.append(self._annotation_snapshot(item))

        return annotations

    def set_rect_annotations(self, rects: list[dict[str, Any]]) -> None:
        self.clear_annotations()
        if not self.has_image():
            return

        image_rect = self._image_rect()
        for rect_data in rects:
            rect = self._rect_from_annotation(rect_data)
            rect = rect.intersected(image_rect)
            if rect.width() < RECT_MIN_SIZE or rect.height() < RECT_MIN_SIZE:
                continue

            item = self._make_rect_item(rect)
            item.setData(
                ANNOTATION_DATA_ROLE,
                self._normalize_annotation_properties({**rect_data, "status": rect_data.get("status", "verified")}),
            )
            self._scene.addItem(item)
            self._annotations.append(item)
            self._update_badge(item)
        self.selected_annotation_changed.emit(None)

    def mousePressEvent(self, event) -> None:
        if (
            self._annotation_enabled
            and self._tool_mode == "rectangle"
            and event.button() == Qt.LeftButton
            and self._drawing_blocked_reason
        ):
            self.drawing_blocked.emit(self._drawing_blocked_reason)
            event.accept()
            return

        if self._can_draw_rectangle(event):
            scene_pos = self._clamp_to_image(self.mapToScene(event.position().toPoint()))
            self._scene.clearSelection()
            self._draft_origin = scene_pos
            self._draft_rect_item = self._make_rect_item(QRectF(scene_pos, scene_pos), preview=True)
            self._scene.addItem(self._draft_rect_item)
            event.accept()
            return

        if self._annotation_enabled and self._tool_mode == "select" and event.button() == Qt.LeftButton:
            scene_item = self.itemAt(event.position().toPoint())
            if scene_item is None or scene_item is self._pixmap_item:
                selected = self._selected_annotation_item()
                if selected:
                    if self._is_confirmed(selected):
                        self.clear_selection()
                    event.accept()
                    return

        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            selected = self._selected_annotation_item()
            if selected and self._is_confirmed(selected):
                self.clear_selection()
                event.accept()
                return

        super().keyPressEvent(event)

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
                self._draft_rect_item.setData(
                    ANNOTATION_DATA_ROLE,
                    self._normalize_annotation_properties({**self._default_annotation_properties, "status": "pending"}),
                )
                self._annotations.append(self._draft_rect_item)
                self._draft_rect_item.setSelected(True)
                self._update_annotation_styles()
                self.selected_annotation_changed.emit(self._annotation_snapshot(self._draft_rect_item))

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
            item.setData(ANNOTATION_DATA_ROLE, self._normalize_annotation_properties({}))

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
            item.setPen(self._annotation_pen_for_item(item, selected=selected))
            item.setBrush(self._annotation_brush_for_item(item, selected=selected))
            self._update_badge(item)

    def _handle_selection_changed(self) -> None:
        if self._selection_update_in_progress:
            return

        selected_annotations = [item for item in self._scene.selectedItems() if item in self._annotations]
        if len(selected_annotations) > 1:
            self._selection_update_in_progress = True
            keep = selected_annotations[-1]
            for item in selected_annotations:
                item.setSelected(item is keep)
            self._selection_update_in_progress = False
            selected_annotations = [keep]

        self._update_annotation_styles()
        if selected_annotations:
            self.selected_annotation_changed.emit(self._annotation_snapshot(selected_annotations[0]))
        else:
            self.selected_annotation_changed.emit(None)

    def _selected_annotation_item(self) -> QGraphicsRectItem | None:
        for item in self._scene.selectedItems():
            if item in self._annotations:
                return item

        return None

    def _annotation_snapshot(self, item: QGraphicsRectItem) -> dict[str, Any]:
        rect = item.rect().normalized()
        return {
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
            "annotation_item_id": self._annotation_item_id(item),
            **self._item_properties(item),
        }

    def _annotation_item_id(self, item: QGraphicsRectItem) -> str:
        return str(id(item))

    def _item_properties(self, item: QGraphicsRectItem) -> dict[str, Any]:
        data = item.data(ANNOTATION_DATA_ROLE)
        if not isinstance(data, dict):
            data = {}

        return self._normalize_annotation_properties(data)

    def _normalize_annotation_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(DEFAULT_ANNOTATION_PROPERTIES)
        normalized.update({key: properties[key] for key in normalized if key in properties})
        normalized["label"] = str(normalized.get("label") or "crack")
        normalized["source"] = str(normalized.get("source") or "manual")
        normalized["status"] = str(normalized.get("status") or "pending")
        normalized["notes"] = str(normalized.get("notes") or "")
        normalized["exportable_to_mask"] = bool(normalized.get("exportable_to_mask", True))

        confidence = normalized.get("confidence")
        normalized["confidence"] = None if confidence in (None, "") else float(confidence)
        return normalized

    def _is_pending(self, item: QGraphicsRectItem) -> bool:
        return self._item_properties(item).get("status") == "pending"

    def _is_confirmed(self, item: QGraphicsRectItem) -> bool:
        return not self._is_pending(item)

    def _annotation_pen_for_item(self, item: QGraphicsRectItem, selected: bool) -> QPen:
        if self._is_pending(item):
            pen = QPen(QColor("#f59e0b"), 2.0)
            pen.setStyle(Qt.DashLine)
            pen.setCosmetic(True)
            return pen

        return self._annotation_pen(selected=selected)

    def _annotation_brush_for_item(self, item: QGraphicsRectItem, selected: bool) -> QBrush:
        if self._is_pending(item):
            return QBrush(QColor(245, 158, 11, 50))

        return self._annotation_brush(selected=selected)

    def _update_badge(self, item: QGraphicsRectItem) -> None:
        badge_rect = getattr(item, "_label_badge_rect", None)
        badge_text = getattr(item, "_label_badge_text", None)

        if self._is_pending(item):
            if badge_rect:
                badge_rect.setVisible(False)
            if badge_text:
                badge_text.setVisible(False)
            return

        if badge_rect is None:
            badge_rect = QGraphicsRectItem(item)
            badge_rect.setZValue(20)
            badge_rect.setBrush(QBrush(QColor("#0b121a")))
            badge_rect.setPen(QPen(QColor("#22d3ee"), 1.0))
            setattr(item, "_label_badge_rect", badge_rect)

        if badge_text is None:
            badge_text = QGraphicsTextItem(item)
            badge_text.setZValue(21)
            badge_text.setDefaultTextColor(QColor("#e6fbff"))
            font = badge_text.font()
            font.setPointSize(8)
            font.setBold(True)
            badge_text.setFont(font)
            setattr(item, "_label_badge_text", badge_text)

        label = str(self._item_properties(item).get("label") or "crack")
        badge_text.setPlainText(label)
        text_rect = badge_text.boundingRect()
        width = max(34.0, text_rect.width() + 10.0)
        height = text_rect.height() + 2.0
        item_rect = item.rect().normalized()
        badge_rect.setRect(item_rect.left(), item_rect.top() - height, width, height)
        badge_text.setPos(item_rect.left() + 5.0, item_rect.top() - height - 1.0)
        badge_rect.setVisible(True)
        badge_text.setVisible(True)

    def _rect_from_annotation(self, annotation: dict[str, Any]) -> QRectF:
        if "bbox" in annotation and isinstance(annotation["bbox"], list) and len(annotation["bbox"]) == 4:
            x, y, width, height = annotation["bbox"]
        else:
            x = annotation.get("x", 0.0)
            y = annotation.get("y", 0.0)
            width = annotation.get("width", 0.0)
            height = annotation.get("height", 0.0)

        return QRectF(float(x), float(y), float(width), float(height)).normalized()

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
