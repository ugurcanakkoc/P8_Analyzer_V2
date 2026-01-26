"""
OCR comparison worker - crash-proof implementation.
"""
from PyQt5.QtCore import pyqtSignal
import pymupdf
import traceback

from .worker import SafeWorker


class OCRComparisonWorker(SafeWorker):
    """
    Worker for comparing PDF text layer vs OCR results.
    Inherits crash protection from SafeWorker.
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, pdf_path, page_num, analysis_result):
        super().__init__(worker_name=f"OCRWorker(page={page_num})")
        self.pdf_path = pdf_path
        self.page_num = page_num
        self.analysis_result = analysis_result
        self._doc = None

    def cleanup(self):
        """Close PDF document."""
        if self._doc:
            try:
                self._doc.close()
                self.debug("PDF document closed")
            except Exception as e:
                self.error_log(f"Failed to close PDF: {e}")
            self._doc = None

        # Always emit finished signal
        try:
            self.finished_signal.emit()
        except Exception:
            pass

    def stop(self):
        """Stop the worker (alias for cancel)."""
        self.cancel()

    def do_work(self):
        """Run OCR comparison."""
        from p8_analyzer.text import HybridTextEngine, SearchProfile, SearchDirection

        self.log_signal.emit("OCR Motoru ve Belge Hazirlaniyor...")

        # Open document
        self._doc = pymupdf.open(self.pdf_path)
        page = self._doc.load_page(self.page_num - 1)

        # Initialize text engine
        engine = HybridTextEngine(languages=['en'])
        engine.load_page(page)

        profile = SearchProfile(
            search_radius=30.0,
            direction=SearchDirection.ANY,
            use_ocr_fallback=True
        )

        # Check for structural groups
        if not hasattr(self.analysis_result, 'structural_groups'):
            self.log_signal.emit("No structural groups found in analysis result")
            return

        count = len(self.analysis_result.structural_groups)
        self.log_signal.emit(f"Toplam {count} hat taranacak...")

        for i, group in enumerate(self.analysis_result.structural_groups):
            if self.is_cancelled():
                self.log_signal.emit("Islem iptal edildi.")
                break

            net_id = f"NET-{i+1:03d}"

            # Get points to scan
            points_to_scan = []
            if hasattr(group, 'elements') and group.elements:
                points_to_scan = [group.elements[0].start_point]

            for pt in points_to_scan:
                try:
                    # PDF vs OCR comparison
                    pdf_res = engine.find_text_only_pdf(pt, profile)
                    ocr_res = engine.find_text_only_ocr(pt, profile)

                    pdf_txt = pdf_res.text if pdf_res else "---"
                    ocr_txt = ocr_res.text if ocr_res else "---"

                    if pdf_txt != "---" or ocr_txt != "---":
                        if pdf_txt == ocr_txt:
                            match_state = "[OK]"
                        elif pdf_txt == "---":
                            match_state = "[OCR Only]"
                        elif ocr_txt == "---":
                            match_state = "[PDF Only]"
                        else:
                            match_state = "[DIFFERENT]"

                        self.log_signal.emit(f"{net_id}: PDF[{pdf_txt}] - OCR[{ocr_txt}] {match_state}")

                except Exception as e:
                    self.error_log(f"Error scanning {net_id}: {e}")

        self.log_signal.emit("Islem Tamamlandi.")
