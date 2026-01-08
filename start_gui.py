import sys
import os
import io
import argparse

# Fix Windows console encoding for UTF-8 (umlauts, special chars)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# IMPORTANT: Import torch BEFORE PyQt5 to prevent DLL conflicts on Windows
# This is needed for the schematic page classifier feature
try:
    import torch
except ImportError:
    pass  # torch is optional, only needed for schematic filter

from PyQt5.QtWidgets import QApplication

# Proje ana dizinini sistem yoluna ekle
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from p8_analyzer.gui import MainWindow
from p8_analyzer.gui.i18n import set_language, get_supported_languages


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="P8 Analyzer - Professional Vector Analyzer for Electrical Schematics"
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=get_supported_languages(),
        default="en",
        help="Set the UI language (en=English, de=German, tr=Turkish). Default: en"
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Parse arguments before QApplication consumes sys.argv
    args = parse_args()

    # Set the language
    set_language(args.lang)

    app = QApplication(sys.argv)

    # Windows'ta ikonların düzgün görünmesi için
    try:
        import ctypes
        myappid = 'mycompany.myproduct.subproduct.version'  # keyfi bir ID
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except:
        pass

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
