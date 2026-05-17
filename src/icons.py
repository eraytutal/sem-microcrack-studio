from __future__ import annotations

import qtawesome as qta
from PySide6.QtGui import QIcon


ACCENT = "#22d3ee"
MUTED = "#94a3b8"


_ICON_NAMES = {
    "app": "fa5s.microscope",
    "assisted": "fa5s.search-location",
    "manual": "fa5s.draw-polygon",
    "export": "fa5s.database",
    "open_image": "fa5s.image",
    "open_folder": "fa5s.folder-open",
    "detect": "fa5s.bolt",
    "save": "fa5s.save",
    "select": "fa5s.mouse-pointer",
    "rectangle": "fa5s.vector-square",
    "polygon": "fa5s.draw-polygon",
    "delete": "fa5s.trash-alt",
    "undo": "fa5s.undo",
    "redo": "fa5s.redo",
    "zoom_in": "fa5s.search-plus",
    "zoom_out": "fa5s.search-minus",
    "fit": "fa5s.expand-arrows-alt",
    "accept": "fa5s.check",
    "reject": "fa5s.times",
    "edit": "fa5s.edit",
    "report": "fa5s.file-alt",
}


def icon(name: str, color: str = MUTED, active: bool = False) -> QIcon:
    icon_name = _ICON_NAMES.get(name, "fa5s.circle")
    return qta.icon(icon_name, color=ACCENT if active else color)
