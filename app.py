import sys

from PySide6.QtWidgets import QApplication

from src.main_window import MainWindow
from src.style import load_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SEM Microcrack Studio")
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
