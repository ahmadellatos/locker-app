"""
main.py
Entry point Digital Locker dengan Loguru dan kapabilitas System Tray.
"""

import os
import sys
from loguru import logger
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

# Setup Loguru: Rotasi log otomatis jika melebihi 10MB
logger.add(
    "digital_locker.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function} - {message}",
)

from ui.app import AppBrankas


def main():
    app = QApplication(sys.argv)

    # Mencegah aplikasi terbunuh total (exit) ketika window ditutup (X).
    # Agar bisa berjalan terus di System Tray (background).
    app.setQuitOnLastWindowClosed(False)

    window = AppBrankas()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
