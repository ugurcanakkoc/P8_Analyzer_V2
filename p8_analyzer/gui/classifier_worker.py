"""
Background worker for page classification - crash-proof implementation.

Scans PDF pages using the YOLO classifier model to identify
schematic pages vs non-schematic pages.
"""

from PyQt5.QtCore import pyqtSignal
import pymupdf
import os
import tempfile
from pathlib import Path

from .worker import SafeWorker


class PageClassifierWorker(SafeWorker):
    """
    Background thread for scanning pages with the classifier model.
    Inherits crash protection from SafeWorker.
    """

    # Signals
    progress = pyqtSignal(int, int)  # current_page, total_pages
    page_classified = pyqtSignal(int, str, float)  # page_num, class_name, confidence
    finished = pyqtSignal(list)  # list of schematic page numbers

    def __init__(self, pdf_path: str, total_pages: int, model_path: str = None):
        super().__init__(worker_name="PageClassifierWorker")
        self.pdf_path = pdf_path
        self.total_pages = total_pages
        self.model_path = model_path or str(
            Path(__file__).parent.parent / "models" / "page_classifier.pt"
        )
        self._doc = None
        self._tmp_path = None
        self._schematic_pages = []

    def cleanup(self):
        """Clean up resources."""
        # Close PDF
        if self._doc:
            try:
                self._doc.close()
                self.debug("PDF document closed")
            except Exception as e:
                self.error_log(f"Failed to close PDF: {e}")
            self._doc = None

        # Remove temp file
        if self._tmp_path and os.path.exists(self._tmp_path):
            try:
                os.unlink(self._tmp_path)
                self.debug("Temp file removed")
            except Exception as e:
                self.error_log(f"Failed to remove temp file: {e}")

        # Emit finished signal with whatever results we have
        try:
            self.finished.emit(self._schematic_pages)
        except Exception:
            pass

    def do_work(self):
        """Run the classification scan."""
        # Check model exists
        if not os.path.exists(self.model_path):
            self.error.emit(f"Model not found: {self.model_path}")
            return

        # Load model
        self.info("Loading YOLO classifier model...")
        try:
            from ultralytics import YOLO
            model = YOLO(self.model_path)
        except ImportError:
            self.error.emit("ultralytics package not installed")
            return
        except Exception as e:
            self.error.emit(f"Failed to load model: {e}")
            return

        # Open PDF
        self.info(f"Opening PDF: {self.pdf_path}")
        self._doc = pymupdf.open(self.pdf_path)

        # Create temp file for classification
        temp_dir = tempfile.gettempdir()
        self._tmp_path = os.path.join(temp_dir, "p8_classifier_temp.png")

        self.info(f"Scanning {self.total_pages} pages...")

        for page_num in range(1, self.total_pages + 1):
            if self.is_cancelled():
                self.info("Scan cancelled")
                break

            try:
                # Emit progress
                self.safe_emit(self.progress, page_num, self.total_pages)

                # Render page
                page = self._doc.load_page(page_num - 1)
                mat = pymupdf.Matrix(150/72, 150/72)  # 150 DPI
                pix = page.get_pixmap(matrix=mat)
                pix.save(self._tmp_path)

                # Classify
                results = model.predict(self._tmp_path, verbose=False)

                if results and len(results) > 0:
                    probs = results[0].probs
                    if probs is not None:
                        top_class = probs.top1
                        class_name = results[0].names[top_class]
                        confidence = float(probs.top1conf)

                        self.safe_emit(self.page_classified, page_num, class_name, confidence)

                        if class_name == "schematic":
                            self._schematic_pages.append(page_num)
                            self.debug(f"Page {page_num}: schematic ({confidence:.2%})")

            except Exception as e:
                self.error_log(f"Page {page_num}: {e}")
                # Continue to next page instead of stopping

        self.info(f"Scan complete: {len(self._schematic_pages)} schematic pages found")
