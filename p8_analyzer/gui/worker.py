"""
Crash-proof worker classes for P8 Analyzer GUI.

All workers inherit from SafeWorker which guarantees:
1. No unhandled exceptions can crash the GUI
2. All errors are logged and emitted via error signal
3. Cleanup always runs via finally blocks
"""
from PyQt5.QtCore import QThread, pyqtSignal
import pymupdf
import traceback
import logging
import sys
from typing import Optional, Any
from datetime import datetime

# Configure logging for workers
logger = logging.getLogger("p8_analyzer.gui.worker")
logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class SafeWorker(QThread):
    """
    Base class for all GUI workers with built-in crash protection.

    Guarantees:
    - No exception can propagate to crash the GUI
    - All errors are captured and emitted via error signal
    - Resources are always cleaned up
    - Comprehensive logging of all operations
    """
    # Signals - subclasses should NOT override these
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, worker_name: str = "SafeWorker"):
        super().__init__()
        self._worker_name = worker_name
        self._start_time: Optional[datetime] = None
        self._is_cancelled = False

    def _log(self, level: str, message: str):
        """Internal logging with worker name prefix."""
        full_msg = f"[{self._worker_name}] {message}"

        if level == "DEBUG":
            logger.debug(full_msg)
        elif level == "INFO":
            logger.info(full_msg)
        elif level == "WARNING":
            logger.warning(full_msg)
        elif level == "ERROR":
            logger.error(full_msg)
        elif level == "CRITICAL":
            logger.critical(full_msg)

        # Also emit to GUI log if connected
        try:
            self.log_message.emit(f"[{level}] {full_msg}")
        except Exception:
            pass  # Signal might not be connected yet

    def debug(self, msg: str):
        self._log("DEBUG", msg)

    def info(self, msg: str):
        self._log("INFO", msg)

    def warning(self, msg: str):
        self._log("WARNING", msg)

    def error_log(self, msg: str):
        self._log("ERROR", msg)

    def critical(self, msg: str):
        self._log("CRITICAL", msg)

    def cancel(self):
        """Request cancellation of the worker."""
        self._is_cancelled = True
        self.info("Cancellation requested")

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._is_cancelled

    def run(self):
        """
        Thread entry point - NEVER override this directly.
        Override do_work() instead.
        """
        self._start_time = datetime.now()
        self.info("Worker started")

        try:
            # Call the actual work method
            self.do_work()

        except Exception as e:
            # Catch ANY exception - this is the crash prevention
            error_msg = f"Unhandled exception: {str(e)}\n{traceback.format_exc()}"
            self.critical(error_msg)

            try:
                self.error.emit(f"[WORKER ERROR] {self._worker_name}:\n{error_msg}")
            except Exception:
                pass  # Even signal emission can fail

        finally:
            # Always run cleanup
            try:
                self.cleanup()
            except Exception as e:
                self.error_log(f"Cleanup failed: {e}")

            # Log completion time
            if self._start_time:
                elapsed = (datetime.now() - self._start_time).total_seconds()
                self.info(f"Worker finished in {elapsed:.2f}s")

    def do_work(self):
        """
        Override this method to implement worker logic.
        Any exception here will be caught and logged.
        """
        raise NotImplementedError("Subclasses must implement do_work()")

    def cleanup(self):
        """
        Override this method for resource cleanup.
        Called in finally block - guaranteed to run.
        """
        pass

    def safe_emit(self, signal, *args):
        """Safely emit a signal, catching any errors."""
        try:
            signal.emit(*args)
        except Exception as e:
            self.error_log(f"Failed to emit signal: {e}")


class AnalysisWorker(SafeWorker):
    """
    Worker for PDF page analysis.
    Uses the shared AnalysisEngine for consistency with CLI.
    Crash-proof implementation with comprehensive logging.
    """
    finished = pyqtSignal(object)
    # New signal for PageAnalysis from AnalysisEngine
    page_analysis_ready = pyqtSignal(object)

    def __init__(self, pdf_path: str, page_num: int):
        super().__init__(worker_name=f"AnalysisWorker(page={page_num})")
        self.pdf_path = pdf_path
        self.page_num = page_num
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

    def do_work(self):
        """Run the analysis pipeline using shared AnalysisEngine."""
        from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
        from p8_analyzer.core.analysis_engine import AnalysisEngine, AnalysisOptions

        # Step 1: Open PDF
        self.info(f"Opening PDF: {self.pdf_path}")
        self._doc = pymupdf.open(self.pdf_path)

        page_index = self.page_num - 1
        if page_index < 0 or page_index >= len(self._doc):
            self.error.emit(f"Invalid page number: {self.page_num}")
            return

        page = self._doc.load_page(page_index)
        self.debug(f"Loaded page {self.page_num} (size: {page.rect.width}x{page.rect.height})")

        # Step 2: Get drawings
        drawings = page.get_drawings()
        if not drawings:
            self.warning("No vector data found on this page")
            self.error.emit("Bu sayfada vektor verisi bulunamadi.")
            return
        self.info(f"Found {len(drawings)} drawing elements")

        # Step 3: Vector Analysis (needed for visualization)
        self.info("Running vector analysis...")
        analysis_result = analyze_page_vectors(drawings, page.rect, self.page_num, DEFAULT_CONFIG)
        self.info(f"Vector analysis complete: {len(analysis_result.structural_groups)} structural groups")

        # Step 4: Run full analysis using shared AnalysisEngine
        self.info("Running AnalysisEngine for terminals, components, pins, and connections...")
        options = AnalysisOptions(
            include_terminals=True,
            include_clusters=True,
            include_wire_annotations=True,
            include_connections=True,
            include_pins=True
        )
        engine = AnalysisEngine(options)
        page_analysis = engine.analyze_page(page, self.page_num)

        # Store PageAnalysis in the vector result for GUI access
        analysis_result.page_analysis = page_analysis

        # Also store legacy terminal format for backward compatibility
        analysis_result.terminals = [
            {
                'center': (t.center_x, t.center_y),
                'radius': t.radius,
                'label': t.label,
                'group_label': t.group_label,
                'full_label': t.full_label,
                'group_id': t.structural_group_id,
            }
            for t in page_analysis.terminals
        ]

        # Store clusters from the engine
        if hasattr(engine, '_clusters'):
            analysis_result.component_clusters = engine._clusters

        self.info(f"Analysis complete: {len(page_analysis.terminals)} terminals, "
                  f"{len(page_analysis.components)} components, "
                  f"{len(page_analysis.connections)} connections")

        # Emit results
        self.info("Emitting analysis result")
        self.safe_emit(self.finished, analysis_result)
        self.safe_emit(self.page_analysis_ready, page_analysis)
