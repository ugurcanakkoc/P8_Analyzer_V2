# MainWindow implementation for P8 Analyzer
# CRASH-PROOF VERSION: All operations wrapped for safety

import os
import json
import traceback
import logging
import sys
from pathlib import Path
from datetime import datetime
from functools import wraps

import pymupdf
from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QToolBar, QAction,
    QDockWidget, QTextEdit, QLabel, QMessageBox, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent, QColor, QBrush

# Local modules
from .viewer import InteractiveGraphicsView
from .worker import AnalysisWorker
from .ocr_worker import OCRComparisonWorker
from .classifier_worker import PageClassifierWorker
from .i18n import t

# P8 Analyzer modules
from p8_analyzer.circuit import check_intersections, CircuitComponent
from p8_analyzer.detection import PinFinder
from p8_analyzer.detection.label_matcher import LabelMatcher
from p8_analyzer.detection.busbar_finder import BusbarFinder
from p8_analyzer.detection.component_namer import ComponentNamer
from p8_analyzer.text import HybridTextEngine

# Configure logging
logger = logging.getLogger("p8_analyzer.gui.main_window")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def crash_proof(method):
    """
    Decorator that makes any method crash-proof.
    Catches all exceptions and logs them instead of crashing.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            error_msg = f"[ERROR] {method.__name__}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            if hasattr(self, 'log'):
                self.log(error_msg)
            return None
    return wrapper


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("window_title"))
        self.resize(1200, 800)

        # State variables
        self.doc = None
        self.current_page = 1
        self.total_pages = 0
        self.app_settings = {"pin_search_radius": 75.0}
        self.text_engine = None
        self.current_result = None
        self.pdf_path = None

        # Classification mode state
        self.classification_mode = False
        self.page_classifications = {}  # {page_num: "schematic" | "non_schematic"}

        # Schematic filter state
        self.schematic_filter_active = False
        self.schematic_pages = []  # List of page numbers that are schematics
        self.page_classifier = None  # YOLO classifier model

        self.init_ui()
        self.load_default_file()

    @crash_proof
    def init_ui(self):
        self.viewer = InteractiveGraphicsView()
        self.setCentralWidget(self.viewer)

        toolbar = QToolBar(t("toolbar_name"))
        self.addToolBar(toolbar)

        act_open = QAction(f"[O] {t('btn_open_pdf')}", self)
        act_open.triggered.connect(self.browse_pdf)
        toolbar.addAction(act_open)
        toolbar.addSeparator()

        self.act_prev = QAction(f"< {t('btn_prev')}", self)
        self.act_prev.triggered.connect(self.prev_page)
        self.act_prev.setEnabled(False)
        toolbar.addAction(self.act_prev)

        self.lbl_page = QLabel(f" {t('page_label_empty')} ")
        toolbar.addWidget(self.lbl_page)

        self.act_next = QAction(f"{t('btn_next')} >", self)
        self.act_next.triggered.connect(self.next_page)
        self.act_next.setEnabled(False)
        toolbar.addAction(self.act_next)
        toolbar.addSeparator()

        self.act_analyze = QAction(f"[A] {t('btn_analyze')}", self)
        self.act_analyze.triggered.connect(self.start_analysis)
        self.act_analyze.setEnabled(False)
        toolbar.addAction(self.act_analyze)
        toolbar.addSeparator()

        self.act_ocr_test = QAction(f"[T] {t('btn_ocr_test')}", self)
        self.act_ocr_test.triggered.connect(self.run_ocr_test)
        self.act_ocr_test.setEnabled(False)
        toolbar.addAction(self.act_ocr_test)

        self.act_nav = QAction(f"[N] {t('btn_navigate')}", self)
        self.act_nav.setCheckable(True)
        self.act_nav.setChecked(True)
        self.act_nav.triggered.connect(lambda: self.set_mode("NAVIGATE"))
        toolbar.addAction(self.act_nav)

        self.act_draw = QAction(f"[D] {t('btn_draw_box')}", self)
        self.act_draw.setCheckable(True)
        self.act_draw.triggered.connect(lambda: self.set_mode("DRAW"))
        toolbar.addAction(self.act_draw)

        self.act_check = QAction(f"[K] {t('btn_connection_check')}", self)
        self.act_check.triggered.connect(self.run_connection_check)
        self.act_check.setEnabled(False)
        toolbar.addAction(self.act_check)

        toolbar.addSeparator()

        # Classification mode toggle
        self.act_classify = QAction(f"[C] {t('btn_classify_mode')}", self)
        self.act_classify.setCheckable(True)
        self.act_classify.triggered.connect(self.toggle_classification_mode)
        self.act_classify.setEnabled(False)
        toolbar.addAction(self.act_classify)

        self.act_save_class = QAction(f"[S] {t('btn_save_classifications')}", self)
        self.act_save_class.triggered.connect(self.save_classifications)
        self.act_save_class.setEnabled(False)
        toolbar.addAction(self.act_save_class)

        # Classification status label
        self.lbl_class_status = QLabel("")
        toolbar.addWidget(self.lbl_class_status)

        toolbar.addSeparator()

        # Schematic filter toggle
        self.act_schematic_filter = QAction(f"[F] {t('btn_schematic_filter')}", self)
        self.act_schematic_filter.setCheckable(True)
        self.act_schematic_filter.triggered.connect(self.toggle_schematic_filter)
        self.act_schematic_filter.setEnabled(False)
        toolbar.addAction(self.act_schematic_filter)

        # Cluster boxes toggle (default ON)
        self.act_cluster_toggle = QAction(f"[B] {t('btn_cluster_boxes')}", self)
        self.act_cluster_toggle.setCheckable(True)
        self.act_cluster_toggle.setChecked(True)  # Default ON
        self.act_cluster_toggle.triggered.connect(self.toggle_cluster_boxes)
        toolbar.addAction(self.act_cluster_toggle)

        # Docks
        dock_log = QDockWidget(t("dock_logs"), self)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        dock_log.setWidget(self.log_text)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_log)

        dock_table = QDockWidget(t("dock_connections"), self)
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(4)
        self.conn_table.setHorizontalHeaderLabels([
            t("header_line_bus"), t("header_pin_end"), t("header_target"), t("header_pin")
        ])
        header = self.conn_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.conn_table.setAlternatingRowColors(False)  # We'll handle row colors manually
        self.conn_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.conn_table.setSelectionMode(QTableWidget.SingleSelection)
        self.conn_table.itemSelectionChanged.connect(self.on_connection_selected)
        dock_table.setWidget(self.conn_table)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_table)

        # Store connection row data (net_id -> group_index mapping)
        self._connection_row_data = []
        # Store PageAnalysis from AnalysisEngine for connection reporting
        self.current_page_analysis = None

        self.status_bar = self.statusBar()

    @crash_proof
    def load_default_file(self):
        base_dir = os.getcwd()
        default_path = os.path.join(base_dir, "data", "ornek.pdf")
        if os.path.exists(default_path):
            self.log(t("msg_auto_loading", path=default_path))
            if self.load_pdf_file(default_path):
                target_page = 27
                if target_page <= self.total_pages:
                    self.current_page = target_page
                    self.load_current_page()
        else:
            self.log(t("msg_file_not_found", path=default_path))

    @crash_proof
    def browse_pdf(self, checked=False):
        path, _ = QFileDialog.getOpenFileName(self, t("msg_select_pdf"), "", "PDF (*.pdf)")
        if path and self.load_pdf_file(path):
            self.current_page = 1
            self.load_current_page()

    @crash_proof
    def load_pdf_file(self, path):
        try:
            if self.doc:
                self.doc.close()
            self.doc = pymupdf.open(path)
            self.total_pages = len(self.doc)
            self.text_engine = None
            self.pdf_path = path
            self.page_classifications = {}  # Reset classifications for new document
            self.act_classify.setEnabled(True)
            # Reset schematic filter state
            self.schematic_filter_active = False
            self.schematic_pages = []
            self.act_schematic_filter.setChecked(False)
            self.act_schematic_filter.setEnabled(True)
            logger.info(f"Loaded PDF: {path} ({self.total_pages} pages)")
            return True
        except Exception as e:
            logger.error(f"Failed to load PDF: {e}")
            QMessageBox.critical(self, t("msg_error"), str(e))
            return False

    @crash_proof
    def load_current_page(self):
        if not self.doc:
            return
        try:
            page = self.doc.load_page(self.current_page - 1)
            self.viewer.set_background_image(page)

            # Update page label based on filter state
            if self.schematic_filter_active and self.schematic_pages:
                idx = self.schematic_pages.index(self.current_page) + 1 if self.current_page in self.schematic_pages else 0
                self.lbl_page.setText(f" {t('page_label_filtered', current=self.current_page, total=self.total_pages, idx=idx, count=len(self.schematic_pages))} ")
            else:
                self.lbl_page.setText(f" {t('page_label', current=self.current_page, total=self.total_pages)} ")

            # Update navigation buttons based on filter state
            if self.schematic_filter_active and self.schematic_pages:
                current_idx = self.schematic_pages.index(self.current_page) if self.current_page in self.schematic_pages else -1
                self.act_prev.setEnabled(current_idx > 0)
                self.act_next.setEnabled(current_idx < len(self.schematic_pages) - 1)
            else:
                self.act_prev.setEnabled(self.current_page > 1)
                self.act_next.setEnabled(self.current_page < self.total_pages)

            self.act_analyze.setEnabled(True)
            self.act_check.setEnabled(False)
            self.act_ocr_test.setEnabled(False)
            self.current_result = None
            self.conn_table.setRowCount(0)
            self.update_classification_status()
        except Exception as e:
            self.log(t("msg_page_error", error=e))

    @crash_proof
    def prev_page(self, checked=False):
        if self.schematic_filter_active and self.schematic_pages:
            # Navigate to previous schematic page
            try:
                current_idx = self.schematic_pages.index(self.current_page)
            except ValueError:
                current_idx = 0
            if current_idx > 0:
                self.current_page = self.schematic_pages[current_idx - 1]
                self.load_current_page()
        elif self.current_page > 1:
            self.current_page -= 1
            self.load_current_page()

    @crash_proof
    def next_page(self, checked=False):
        if self.schematic_filter_active and self.schematic_pages:
            # Navigate to next schematic page
            try:
                current_idx = self.schematic_pages.index(self.current_page)
            except ValueError:
                current_idx = -1
            if current_idx < len(self.schematic_pages) - 1:
                self.current_page = self.schematic_pages[current_idx + 1]
                self.load_current_page()
        elif self.current_page < self.total_pages:
            self.current_page += 1
            self.load_current_page()

    @crash_proof
    def set_mode(self, mode):
        self.viewer.set_mode(mode)
        self.act_nav.setChecked(mode == "NAVIGATE")
        self.act_draw.setChecked(mode == "DRAW")
        self.status_bar.showMessage(t("msg_mode", mode=mode))

    @crash_proof
    def start_analysis(self, checked=False):
        if not self.doc:
            return
        self.log(t("msg_analyzing", page=self.current_page))
        self.act_analyze.setEnabled(False)

        self.worker = AnalysisWorker(self.doc.name, self.current_page)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.page_analysis_ready.connect(self.on_page_analysis_ready)
        self.worker.error.connect(self.on_error)
        self.worker.log_message.connect(self.log)  # Connect worker logging
        self.worker.start()

    @crash_proof
    def on_page_analysis_ready(self, page_analysis):
        """Store PageAnalysis from AnalysisEngine for connection reporting."""
        self.current_page_analysis = page_analysis

    @crash_proof
    def on_analysis_finished(self, result):
        """Handle analysis completion - crash-proof."""
        self.act_analyze.setEnabled(True)

        if result is None:
            self.log("[ERROR] Analysis returned no result")
            return

        self.current_result = result

        # Store structural groups in viewer for highlighting
        if hasattr(result, 'structural_groups'):
            self.viewer.set_structural_groups(result.structural_groups)

        # Clear any previous selection highlighting
        self.viewer.clear_highlights()
        self._connection_row_data = []

        # Pass page for PIL-based cluster visualization
        page = None
        try:
            page = self.doc.load_page(self.current_page - 1) if self.doc else None
        except Exception as e:
            self.log(f"[WARNING] Could not load page for visualization: {e}")

        # Draw analysis result with error handling
        try:
            self.viewer.draw_analysis_result(result, page=page)
        except Exception as e:
            self.log(f"[ERROR] Visualization failed: {e}")
            logger.error(f"Visualization failed: {e}\n{traceback.format_exc()}")

        self.act_check.setEnabled(True)
        self.act_ocr_test.setEnabled(True)

        # Log completion
        group_count = 0
        try:
            if hasattr(result, 'structural_groups'):
                group_count = len(result.structural_groups)
        except Exception:
            pass
        self.log(t("msg_analysis_complete", count=group_count))

        # Run connection check with error handling
        try:
            self.run_connection_check()
        except Exception as e:
            self.log(f"[ERROR] Connection check failed: {e}")
            logger.error(f"Connection check failed: {e}\n{traceback.format_exc()}")

    @crash_proof
    def on_error(self, msg):
        self.log(msg)
        self.act_analyze.setEnabled(True)

    @crash_proof
    def run_ocr_test(self, checked=False):
        if not self.current_result or not self.doc:
            return
        self.ocr_worker = OCRComparisonWorker(self.doc.name, self.current_page, self.current_result)
        self.ocr_worker.log_signal.connect(self.log)
        self.ocr_worker.start()

    @crash_proof
    def run_connection_check(self, checked=False):
        """
        Run connection check using AnalysisEngine results.

        Uses the pre-computed connections from PageAnalysis which have proper
        pin detection and path ordering (same as CLI).
        """
        if not self.current_result:
            self.log("[WARNING] No analysis result available")
            return

        # Use PageAnalysis from VectorAnalysisResult (stored by worker)
        page_analysis = getattr(self.current_result, 'page_analysis', None)
        if page_analysis and page_analysis.connections:
            self._generate_connection_report_from_page_analysis(page_analysis)
            return

        # Fallback: No PageAnalysis available, log warning
        self.log("[WARNING] No PageAnalysis available - connection report may be incomplete")

    @crash_proof
    def _generate_connection_report_from_page_analysis(self, page_analysis):
        """
        Generate connection report from PageAnalysis (AnalysisEngine format).

        Uses pre-computed ordered connections with proper pin detection.
        This is the same logic used by the CLI.
        """
        self.log(f"\n{t('msg_connection_report')}")
        self.conn_table.setRowCount(0)
        self._connection_row_data = []

        connections = page_analysis.connections
        if not connections:
            self.log(f"[INFO] {t('msg_no_valid_connections')}")
            return

        # Helper to get base component (e.g., "-X1" from "-X1:2")
        def get_base(comp_id):
            return comp_id.split(":")[0] if ":" in comp_id else comp_id

        # Connections from AnalysisEngine are already ordered pairs (source -> target)
        for conn in connections:
            try:
                source = conn.source_id
                target = conn.target_id
                net_id = conn.net_id

                # Skip same-block connections (e.g., -X1:2 to -X1:1)
                source_base = get_base(source)
                target_base = get_base(target)
                if source_base == target_base:
                    continue

                # Add to table
                self._add_table_row(source, target, net_id)
                self.log(f"[NET] {source} --> {target}")

            except Exception as e:
                logger.debug(f"Error processing connection: {e}")

        if self.conn_table.rowCount() == 0:
            self.log(f"[INFO] {t('msg_no_valid_connections')}")

    @crash_proof
    def _generate_connection_report(self, connections):
        """Generate and display connection report."""
        self.log(f"\n{t('msg_connection_report')}")
        self.conn_table.setRowCount(0)
        self._connection_row_data = []  # Clear row data

        if not connections:
            self.log(f"[INFO] {t('msg_no_valid_connections')}")
            return

        # Sort: Busbars first (non-NET-XXX names), then NET-XXX
        sorted_keys = sorted(connections.keys(), key=lambda k: (k.startswith("NET"), k))

        for net_id in sorted_keys:
            try:
                raw_ids = connections[net_id]
                unique_ids = list(dict.fromkeys(raw_ids))  # Deduplicate

                # 1. Separate busbar and components
                busbar_name = None
                components = []

                for uid in unique_ids:
                    if uid.startswith("[BUSBAR:"):
                        busbar_name = uid.split(":")[1].strip(" ]")
                    else:
                        components.append(uid)

                # 2. Pin check (filter those without pins)
                valid_components = []
                for comp_id in components:
                    if ":" in comp_id:
                        valid_components.append(comp_id)
                    else:
                        self.log(f"[WARNING] {t('msg_warning_no_pin', comp=comp_id, net=net_id)}")

                if not valid_components:
                    continue

                # 3. Source-Target determination and table entry
                if busbar_name:
                    # Scenario A: Busbar as source
                    for target in valid_components:
                        self._add_table_row(busbar_name, target, net_id)
                        self.log(f"[BUSBAR] {busbar_name} ==> {target}")
                else:
                    # Scenario B: Normal connection (Net)
                    terminals = [c for c in valid_components if c.startswith("-X")]
                    devices = [c for c in valid_components if not c.startswith("-X")]

                    if not terminals and not devices:
                        continue

                    # Determine source
                    source = None
                    targets = []

                    if terminals:
                        source = terminals[0]
                        targets = terminals[1:] + devices
                    else:
                        source = devices[0]
                        targets = devices[1:]

                    # Helper to get base component (e.g., "-X1" from "-X1:2")
                    def get_base(comp_id):
                        return comp_id.split(":")[0] if ":" in comp_id else comp_id

                    source_base = get_base(source)

                    # Add to table (filter out same-block connections)
                    for target in targets:
                        target_base = get_base(target)
                        # Skip if same terminal block (e.g., -X1:2 to -X1:1)
                        if source_base == target_base:
                            continue
                        self._add_table_row(source, target, net_id)
                        self.log(f"[NET] {source} --> {target}")

            except Exception as e:
                logger.debug(f"Error processing net {net_id}: {e}")

        if self.conn_table.rowCount() == 0:
            self.log(f"[INFO] {t('msg_no_valid_connections')}")

    @crash_proof
    def _add_table_row(self, source, target, net_id=None):
        row = self.conn_table.rowCount()
        self.conn_table.insertRow(row)

        s_tag, s_pin = self._parse_comp_id(source)
        t_tag, t_pin = self._parse_comp_id(target)

        items = [
            QTableWidgetItem(s_tag),
            QTableWidgetItem(s_pin),
            QTableWidgetItem(t_tag),
            QTableWidgetItem(t_pin)
        ]

        # Get structural group index and color from net_id
        group_index = -1
        row_color = None

        if net_id and net_id.startswith("NET-"):
            try:
                # NET-001 -> index 0
                group_index = int(net_id.split("-")[1]) - 1

                # Get color from structural group
                if self.current_result and hasattr(self.current_result, 'structural_groups'):
                    groups = self.current_result.structural_groups
                    if 0 <= group_index < len(groups):
                        color_hex = groups[group_index].color.lstrip('#')
                        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
                        # Light tint for background (40% opacity effect)
                        row_color = QColor(r, g, b, 50)
            except (ValueError, IndexError, AttributeError):
                pass

        # Set items with background color
        for col, item in enumerate(items):
            if row_color:
                item.setBackground(QBrush(row_color))
            self.conn_table.setItem(row, col, item)

        # Store row data for selection handling
        self._connection_row_data.append({
            'net_id': net_id,
            'group_index': group_index,
            'source': source,
            'target': target
        })

    def _parse_comp_id(self, text):
        if ":" in text:
            parts = text.split(":", 1)
            return parts[0], parts[1]
        return text, ""

    @crash_proof
    def on_connection_selected(self, checked=False):
        """Handle connection table row selection - highlight the wire on screen."""
        selected_rows = self.conn_table.selectionModel().selectedRows()
        if not selected_rows:
            self.viewer.clear_highlights()
            return

        row_index = selected_rows[0].row()

        # Get row data
        if row_index >= len(self._connection_row_data):
            return

        row_data = self._connection_row_data[row_index]
        group_index = row_data.get('group_index', -1)

        if group_index < 0:
            self.viewer.clear_highlights()
            return

        # Get color for highlight
        color_hex = None
        if self.current_result and hasattr(self.current_result, 'structural_groups'):
            groups = self.current_result.structural_groups
            if 0 <= group_index < len(groups):
                color_hex = groups[group_index].color

        # Highlight the structural group
        self.viewer.highlight_structural_group(group_index, color_hex)

    @crash_proof
    def toggle_cluster_boxes(self, checked=False):
        """Toggle cluster box visibility and redraw."""
        show_clusters = self.act_cluster_toggle.isChecked()
        self.viewer.set_clusters_visible(show_clusters)

        # Redraw if we have an analysis result
        if self.current_result and self.doc:
            try:
                page = self.doc.load_page(self.current_page - 1)
                self.viewer.draw_analysis_result(self.current_result, page)

                # Re-apply current highlight if any
                selected_rows = self.conn_table.selectionModel().selectedRows()
                if selected_rows:
                    self.on_connection_selected()

                status = "ON" if show_clusters else "OFF"
                self.log(f"[INFO] Cluster boxes: {status}")
            except Exception as e:
                logger.debug(f"Failed to redraw: {e}")

    def log(self, msg):
        """Log message to GUI and console."""
        try:
            self.log_text.append(str(msg))
            logger.info(msg)
        except Exception:
            print(f"[LOG] {msg}")

    # ========== PAGE CLASSIFICATION METHODS ==========

    @crash_proof
    def toggle_classification_mode(self, checked=False):
        """Toggle classification mode on/off."""
        self.classification_mode = self.act_classify.isChecked()
        if self.classification_mode:
            self.log(t("msg_classification_mode_on"))
            self.status_bar.showMessage(t("msg_classification_mode_on"))
        else:
            self.log(t("msg_classification_mode_off"))
            self.status_bar.showMessage(t("msg_classification_mode_off"))
        self.update_classification_status()

    @crash_proof
    def update_classification_status(self):
        """Update the classification status label for current page."""
        if self.current_page in self.page_classifications:
            status = self.page_classifications[self.current_page]
            if status == "schematic":
                self.lbl_class_status.setText(t("lbl_classification_status", status="S"))
                self.lbl_class_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.lbl_class_status.setText(t("lbl_classification_status", status="N"))
                self.lbl_class_status.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lbl_class_status.setText("")
            self.lbl_class_status.setStyleSheet("")

        # Enable save button if we have any classifications
        self.act_save_class.setEnabled(len(self.page_classifications) > 0)

    @crash_proof
    def classify_page(self, classification: str):
        """Mark current page with given classification."""
        self.page_classifications[self.current_page] = classification
        self.update_classification_status()

        if classification == "schematic":
            self.log(t("msg_classified_schematic", page=self.current_page))
        else:
            self.log(t("msg_classified_non_schematic", page=self.current_page))

        # Show stats
        schematic_count = sum(1 for c in self.page_classifications.values() if c == "schematic")
        non_schematic_count = len(self.page_classifications) - schematic_count
        self.status_bar.showMessage(
            t("msg_classification_stats",
              schematic=schematic_count,
              non_schematic=non_schematic_count,
              total=len(self.page_classifications))
        )

        # Auto-advance to next page
        if self.current_page < self.total_pages:
            self.next_page()

    @crash_proof
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts for classification mode."""
        if self.classification_mode and self.doc:
            key = event.key()
            if key == Qt.Key_S:
                self.classify_page("schematic")
                return
            elif key == Qt.Key_N:
                self.classify_page("non_schematic")
                return
            elif key == Qt.Key_Space:
                # Skip - just go to next page
                if self.current_page < self.total_pages:
                    self.next_page()
                return

        # Pass to parent for other key handling
        super().keyPressEvent(event)

    @crash_proof
    def save_classifications(self, checked=False):
        """Save classifications to JSON and export schematic pages as images."""
        if not self.page_classifications or not self.pdf_path:
            return

        # Create output directory
        pdf_name = Path(self.pdf_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("YOLO/data/classification_output") / f"{pdf_name}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON metadata
        metadata = {
            "pdf_path": str(self.pdf_path),
            "pdf_name": pdf_name,
            "total_pages": self.total_pages,
            "timestamp": timestamp,
            "classifications": {
                str(page): cls for page, cls in self.page_classifications.items()
            }
        }

        json_path = output_dir / "classifications.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Export pages as images for both classes
        schematic_dir = output_dir / "schematic"
        non_schematic_dir = output_dir / "non_schematic"
        schematic_dir.mkdir(exist_ok=True)
        non_schematic_dir.mkdir(exist_ok=True)

        schematic_count = 0
        non_schematic_count = 0

        for page_num, classification in self.page_classifications.items():
            try:
                page = self.doc.load_page(page_num - 1)
                mat = pymupdf.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat)

                if classification == "schematic":
                    img_path = schematic_dir / f"{pdf_name}_page{page_num:04d}.png"
                    pix.save(str(img_path))
                    schematic_count += 1
                else:
                    img_path = non_schematic_dir / f"{pdf_name}_page{page_num:04d}.png"
                    pix.save(str(img_path))
                    non_schematic_count += 1
            except Exception as e:
                self.log(f"[ERROR] Page {page_num}: {e}")

        self.log(t("msg_classifications_saved", path=str(json_path)))
        self.log(f"[INFO] Exported: {schematic_count} schematic, {non_schematic_count} non-schematic to {output_dir}")

        # Show summary
        schematic_count = sum(1 for c in self.page_classifications.values() if c == "schematic")
        non_schematic_count = len(self.page_classifications) - schematic_count
        self.log(t("msg_classification_stats",
                   schematic=schematic_count,
                   non_schematic=non_schematic_count,
                   total=len(self.page_classifications)))

    # ========== SCHEMATIC FILTER METHODS ==========

    @crash_proof
    def toggle_schematic_filter(self, checked=False):
        """Toggle schematic-only page filter on/off."""
        if self.act_schematic_filter.isChecked():
            # Enable filter - scan pages first if needed
            if not self.schematic_pages:
                # Start async scan - activation happens in _on_classifier_finished
                self.scan_schematic_pages()
            else:
                # Already have scan results, just activate
                self.schematic_filter_active = True
                self.log(t("msg_filter_on", count=len(self.schematic_pages)))
                self.status_bar.showMessage(t("msg_filter_on", count=len(self.schematic_pages)))

                # Jump to first schematic page if current page is not a schematic
                if self.current_page not in self.schematic_pages:
                    self.current_page = self.schematic_pages[0]

                self.load_current_page()
        else:
            # Disable filter
            self.schematic_filter_active = False
            self.log(t("msg_filter_off"))
            self.status_bar.showMessage(t("msg_filter_off"))
            self.load_current_page()

    @crash_proof
    def scan_schematic_pages(self):
        """Scan all pages using the page classifier model (background thread)."""
        if not self.doc:
            return

        # Check model exists
        model_path = Path(__file__).parent.parent / "models" / "page_classifier.pt"
        if not model_path.exists():
            self.log(t("msg_model_not_found"))
            QMessageBox.warning(self, t("msg_error"), t("msg_model_not_found"))
            self.act_schematic_filter.setChecked(False)
            return

        self.log(t("msg_filter_scanning"))

        # Create progress dialog
        self.classifier_progress = QProgressDialog(
            t("msg_filter_scanning"), "Cancel", 0, self.total_pages, self
        )
        self.classifier_progress.setWindowTitle(t("btn_schematic_filter"))
        self.classifier_progress.setWindowModality(Qt.WindowModal)
        self.classifier_progress.setMinimumDuration(0)
        self.classifier_progress.setValue(0)

        # Create and start worker
        self.classifier_worker = PageClassifierWorker(
            self.pdf_path, self.total_pages, str(model_path)
        )
        self.classifier_worker.progress.connect(self._on_classifier_progress)
        self.classifier_worker.page_classified.connect(self._on_page_classified)
        self.classifier_worker.finished.connect(self._on_classifier_finished)
        self.classifier_worker.error.connect(self._on_classifier_error)

        # Handle cancel button
        self.classifier_progress.canceled.connect(self._on_classifier_cancelled)

        self.classifier_worker.start()

    @crash_proof
    def _on_classifier_progress(self, current: int, total: int):
        """Update progress dialog during classification."""
        if hasattr(self, 'classifier_progress') and self.classifier_progress:
            self.classifier_progress.setValue(current)
            self.classifier_progress.setLabelText(f"Scanning page {current} / {total}...")

    @crash_proof
    def _on_page_classified(self, page_num: int, class_name: str, confidence: float):
        """Handle individual page classification result."""
        pass  # Could log each classification if verbose mode desired

    @crash_proof
    def _on_classifier_finished(self, schematic_pages: list):
        """Handle classification completion."""
        # Close progress dialog
        if hasattr(self, 'classifier_progress') and self.classifier_progress:
            self.classifier_progress.close()
            self.classifier_progress = None

        self.schematic_pages = schematic_pages or []
        self.log(t("msg_filter_complete", count=len(self.schematic_pages), total=self.total_pages))
        self.status_bar.showMessage(t("msg_filter_complete", count=len(self.schematic_pages), total=self.total_pages))

        # Now activate the filter if we found schematics
        if self.schematic_pages:
            self.schematic_filter_active = True
            self.log(t("msg_filter_on", count=len(self.schematic_pages)))

            # Jump to first schematic page if current page is not a schematic
            if self.current_page not in self.schematic_pages:
                self.current_page = self.schematic_pages[0]

            self.load_current_page()
        else:
            # No schematics found, disable filter
            self.act_schematic_filter.setChecked(False)
            QMessageBox.information(self, t("btn_schematic_filter"),
                                   f"No schematic pages found in {self.total_pages} pages.")

    @crash_proof
    def _on_classifier_error(self, error_msg: str):
        """Handle classification errors."""
        self.log(f"[ERROR] {error_msg}")

    @crash_proof
    def _on_classifier_cancelled(self):
        """Handle user cancellation of classification."""
        if hasattr(self, 'classifier_worker') and self.classifier_worker:
            self.classifier_worker.cancel()
            self.classifier_worker.wait()
        self.log("Classification cancelled by user")
        self.act_schematic_filter.setChecked(False)
