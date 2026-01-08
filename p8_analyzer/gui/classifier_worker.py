"""
Background worker for page classification.

Scans PDF pages using the YOLO classifier model to identify
schematic pages vs non-schematic pages.
"""

from PyQt5.QtCore import QThread, pyqtSignal
import pymupdf
import os
import tempfile
from pathlib import Path


class PageClassifierWorker(QThread):
    """Background thread for scanning pages with the classifier model."""

    # Signals
    progress = pyqtSignal(int, int)  # current_page, total_pages
    page_classified = pyqtSignal(int, str, float)  # page_num, class_name, confidence
    finished = pyqtSignal(list)  # list of schematic page numbers
    error = pyqtSignal(str)

    def __init__(self, pdf_path: str, total_pages: int, model_path: str = None):
        super().__init__()
        self.pdf_path = pdf_path
        self.total_pages = total_pages
        self.model_path = model_path or str(
            Path(__file__).parent.parent / "models" / "page_classifier.pt"
        )
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the scan."""
        self._cancelled = True

    def run(self):
        """Run the classification scan in background."""
        doc = None
        schematic_pages = []

        try:
            # Load model
            from ultralytics import YOLO
            model = YOLO(self.model_path)

            # Open PDF in this thread
            doc = pymupdf.open(self.pdf_path)

            # Temp file for classification
            temp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(temp_dir, "p8_classifier_temp.png")

            for page_num in range(1, self.total_pages + 1):
                if self._cancelled:
                    break

                try:
                    # Emit progress
                    self.progress.emit(page_num, self.total_pages)

                    # Render page
                    page = doc.load_page(page_num - 1)
                    mat = pymupdf.Matrix(150/72, 150/72)  # 150 DPI
                    pix = page.get_pixmap(matrix=mat)
                    pix.save(tmp_path)

                    # Classify
                    results = model.predict(tmp_path, verbose=False)

                    if results and len(results) > 0:
                        probs = results[0].probs
                        if probs is not None:
                            top_class = probs.top1
                            class_name = results[0].names[top_class]
                            confidence = float(probs.top1conf)

                            self.page_classified.emit(page_num, class_name, confidence)

                            if class_name == "schematic":
                                schematic_pages.append(page_num)

                except Exception as e:
                    self.error.emit(f"Page {page_num}: {e}")

            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

            self.finished.emit(schematic_pages)

        except Exception as e:
            self.error.emit(f"Classification failed: {e}")
            self.finished.emit([])

        finally:
            if doc:
                doc.close()
