"""
P8 Analyzer GUI - PyQt5 Application

Provides the graphical user interface for PDF analysis.
"""

from .main_window import MainWindow
from .viewer import InteractiveGraphicsView
from .worker import AnalysisWorker
from .ocr_worker import OCRComparisonWorker
from .i18n import (
    t,
    set_language,
    get_language,
    get_supported_languages,
    TRANSLATIONS,
)

__all__ = [
    "MainWindow",
    "InteractiveGraphicsView",
    "AnalysisWorker",
    "OCRComparisonWorker",
    # i18n
    "t",
    "set_language",
    "get_language",
    "get_supported_languages",
    "TRANSLATIONS",
]
