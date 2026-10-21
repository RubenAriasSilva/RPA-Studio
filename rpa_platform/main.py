import sys
import os

# Add project root to path so imports work regardless of launch location
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RPA Studio")
    app.setOrganizationName("RPA")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    # `--open <path>` is passed by the Orchestrator's "Editar un proceso"
    if "--open" in sys.argv:
        idx = sys.argv.index("--open")
        if idx + 1 < len(sys.argv):
            window.open_file(os.path.abspath(sys.argv[idx + 1]))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
