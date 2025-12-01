# MainWindow implementation for P8 Analyzer

import os
import pymupdf
from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QToolBar, QAction,
    QDockWidget, QTextEdit, QLabel, QMessageBox, QWidget, QVBoxLayout
)
from PyQt5.QtCore import Qt

# Local modules
from .viewer import InteractiveGraphicsView
from .worker import AnalysisWorker
from .circuit_logic import check_intersections, CircuitComponent
from .ocr_worker import OCRComparisonWorker
from src.label_matcher import LabelMatcher
from src.pin_finder import PinFinder
from src.text_engine import HybridTextEngine

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UVP - Professional Vector Analyzer")
        self.resize(1200, 800)

        # State variables
        self.doc = None
        self.current_page = 1
        self.total_pages = 0
        self.app_settings = {"pin_search_radius": 75.0}
        self.debug_dialog = None
        self.text_engine = None

        self.init_ui()
        self.load_default_file()

    # ---------------------------------------------------------------------
    # UI setup
    # ---------------------------------------------------------------------
    def init_ui(self):
        # Viewer (canvas)
        self.viewer = InteractiveGraphicsView()
        self.setCentralWidget(self.viewer)

        # Toolbar
        toolbar = QToolBar("Araçlar")
        self.addToolBar(toolbar)

        # Open PDF
        act_open = QAction("📂 PDF Aç", self)
        act_open.triggered.connect(self.browse_pdf)
        toolbar.addAction(act_open)
        toolbar.addSeparator()

        # Navigation
        self.act_prev = QAction("◀ Önceki", self)
        self.act_prev.triggered.connect(self.prev_page)
        self.act_prev.setEnabled(False)
        toolbar.addAction(self.act_prev)

        self.lbl_page = QLabel(" Sayfa: -/- ")
        toolbar.addWidget(self.lbl_page)

        self.act_next = QAction("Sonraki ▶", self)
        self.act_next.triggered.connect(self.next_page)
        self.act_next.setEnabled(False)
        toolbar.addAction(self.act_next)
        toolbar.addSeparator()

        # Analyse button
        self.act_analyze = QAction("⚡ Analiz Et", self)
        self.act_analyze.triggered.connect(self.start_analysis)
        self.act_analyze.setEnabled(False)
        toolbar.addAction(self.act_analyze)
        toolbar.addSeparator()

        # OCR button
        self.act_ocr_test = QAction("👁️ OCR vs PDF", self)
        self.act_ocr_test.triggered.connect(self.run_ocr_test)
        self.act_ocr_test.setEnabled(False)
        toolbar.addAction(self.act_ocr_test)

        # Mode buttons
        self.act_nav = QAction("✋ Gezin", self)
        self.act_nav.setCheckable(True)
        self.act_nav.setChecked(True)
        self.act_nav.triggered.connect(lambda: self.set_mode("NAVIGATE"))
        toolbar.addAction(self.act_nav)

        self.act_draw = QAction("🟥 Kutu Çiz", self)
        self.act_draw.setCheckable(True)
        self.act_draw.triggered.connect(lambda: self.set_mode("DRAW"))
        toolbar.addAction(self.act_draw)

        # Connection check button
        self.act_check = QAction("🔗 Bağlantı Kontrol", self)
        self.act_check.triggered.connect(self.run_connection_check)
        self.act_check.setEnabled(False)
        toolbar.addAction(self.act_check)

        # Log panel
        dock = QDockWidget("Loglar", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        dock.setWidget(self.log_text)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        # Status bar
        self.status_bar = self.statusBar()

    # ---------------------------------------------------------------------
    # File handling
    # ---------------------------------------------------------------------
    def load_default_file(self):
        """Automatically load data/ornek.pdf and jump to page 18 if possible."""
        base_dir = os.getcwd()
        default_path = os.path.join(base_dir, "data", "ornek.pdf")
        if os.path.exists(default_path):
            self.log(f"Otomatik yükleme: {default_path}")
            if self.load_pdf_file(default_path):
                target_page = 18
                if target_page <= self.total_pages:
                    self.current_page = target_page
                    self.load_current_page()
                else:
                    self.log(f"Uyarı: PDF {self.total_pages} sayfa, 18. sayfa açılamadı.")
        else:
            self.log("Bilgi: 'data/ornek.pdf' bulunamadı, boş açılıyor.")

    def browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF Seç", "", "PDF (*.pdf)")
        if path and self.load_pdf_file(path):
            self.current_page = 1
            self.load_current_page()

    def load_pdf_file(self, path):
        try:
            self.doc = pymupdf.open(path)
            self.total_pages = len(self.doc)
            self.log(f"PDF Yüklendi: {os.path.basename(path)} ({self.total_pages} sayfa)")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF açılamadı:\n{str(e)}")
            return False

    def load_current_page(self):
        if not self.doc:
            return
        try:
            page_index = self.current_page - 1
            page = self.doc.load_page(page_index)
            self.viewer.set_background_image(page)
            self.status_bar.showMessage(f"Sayfa {self.current_page} yüklendi.")
            self.lbl_page.setText(f" Sayfa: {self.current_page} / {self.total_pages} ")
            self.act_prev.setEnabled(self.current_page > 1)
            self.act_next.setEnabled(self.current_page < self.total_pages)
            self.act_analyze.setEnabled(True)
            self.act_check.setEnabled(False)
            if hasattr(self, "current_result"):
                del self.current_result
        except Exception as e:
            self.log(f"Sayfa yükleme hatası: {e}")

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_current_page()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_current_page()

    def set_mode(self, mode):
        if mode == "NAVIGATE":
            self.act_nav.setChecked(True)
            self.act_draw.setChecked(False)
            self.viewer.set_mode("NAVIGATE")
            self.status_bar.showMessage("Mod: Gezinme")
        else:
            self.act_nav.setChecked(False)
            self.act_draw.setChecked(True)
            self.viewer.set_mode("DRAW")
            self.status_bar.showMessage("Mod: Kutu Çizme (Hattın ucuna kutu çizin)")

    # ---------------------------------------------------------------------
    # Analysis workflow
    # ---------------------------------------------------------------------
    def start_analysis(self):
        self.log(f"Sayfa {self.current_page} için analiz başlatılıyor...")
        self.act_analyze.setEnabled(False)
        self.status_bar.showMessage("Analiz hesaplanıyor...")
        self.worker = AnalysisWorker(self.doc, self.current_page)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_analysis_finished(self, result):
        self.act_analyze.setEnabled(True)
        self.status_bar.showMessage("Analiz Tamamlandı.")
        self.current_result = result
        self.viewer.draw_analysis_result(result)
        self.act_check.setEnabled(True)
        self.act_ocr_test.setEnabled(True)
        self.log(f"Analiz Bitti. {len(result.structural_groups)} hat bulundu.")
        self.run_connection_check()

    def on_error(self, msg):
        self.log(msg)
        self.act_analyze.setEnabled(True)

    # ---------------------------------------------------------------------
    # OCR comparison (placeholder)
    # ---------------------------------------------------------------------
    def run_ocr_test(self):
        if not hasattr(self, "text_engine"):
            self.text_engine = OCRComparisonWorker(self.doc, self.current_page)
        self.log("OCR test çalıştırıldı (henüz implement edilmedi).")

    # ---------------------------------------------------------------------
    # Connection checking & pin detection
    # ---------------------------------------------------------------------
    def run_connection_check(self):
        manual_boxes = self.viewer.get_drawn_components()
        if not hasattr(self, "current_result"):
            self.log("UYARI: Önce 'Analiz Et' butonuna basmalısınız.")
            return

        # Convert detected terminals to CircuitComponent objects
        terminal_components = []
        if hasattr(self.current_result, "terminals") and self.current_result.terminals:
            for term in self.current_result.terminals:
                cx, cy = term["center"]
                r = term["radius"]
                margin = 2.0
                term_id = term.get("full_label") or f"TERM-{len(terminal_components)+1}"
                comp = CircuitComponent(
                    id=term_id,
                    label="Terminal",
                    bbox={
                        "min_x": cx - r - margin,
                        "min_y": cy - r - margin,
                        "max_x": cx + r + margin,
                        "max_y": cy + r + margin,
                    },
                )
                terminal_components.append(comp)

        all_components = manual_boxes + terminal_components
        connections = check_intersections(all_components, self.current_result)

        # ---- PinFinder integration ----
        if manual_boxes:
            if not self.text_engine:
                self.text_engine = HybridTextEngine(["en"])
                if self.doc:
                    self.text_engine.load_page(self.doc.load_page(self.current_page - 1))
            pin_finder = PinFinder(self.app_settings)
            if self.debug_dialog and self.debug_dialog.isVisible():
                pin_finder.set_debug_callback(self.debug_log)
            for i, group in enumerate(self.current_result.structural_groups):
                net_id = f"NET-{i+1:03d}"
                found_pins = pin_finder.find_pins_for_group(group, manual_boxes, self.text_engine)
                if found_pins:
                    connections.setdefault(net_id, []).extend([p["full_label"] for p in found_pins])

        # ---- LabelMatcher fallback ----
        try:
            matcher = LabelMatcher(self.doc.load_page(self.current_page - 1))
            for i, group in enumerate(self.current_result.structural_groups):
                net_id = f"NET-{i+1:03d}"
                endpoints = []
                lines = getattr(group, "lines", [])
                for line in lines:
                    endpoints.append(line.get("start"))
                    endpoints.append(line.get("end"))
                if endpoints:
                    labels = matcher.find_labels_for_net(endpoints, all_components)
                    if labels:
                        connections.setdefault(net_id, []).extend([f"LABEL:{lbl}" for lbl in labels])
        except Exception as e:
            self.log(f"Label Matcher hatası: {e}")

        # Reporting
        self.log("\n====== BAĞLANTI RAPORU ======")
        found_any = False
        for net_id in sorted(connections.keys()):
            comp_ids = connections[net_id]
            if comp_ids:
                found_any = True
                self.log(f"🔹 {net_id} Hattı:")
                for comp_id in comp_ids:
                    icon = "🔌"
                    if "BOX" in comp_id:
                        icon = "📦"
                    elif "LABEL" in comp_id:
                        icon = "🏷️"
                    self.log(f"   └─ {icon} {comp_id}")
        if not found_any:
            self.log("❌ Hiçbir bağlantı bulunamadı.")
            self.log("İpucu: Klemensler veya kutular hatların üzerine gelmiyor olabilir.")

    # ---------------------------------------------------------------------
    # Logging helpers
    # ---------------------------------------------------------------------
    def log(self, msg):
        self.log_text.append(msg)

    def debug_log(self, msg):
        if self.debug_dialog:
            self.debug_dialog.append_log(msg)

    # ---------------------------------------------------------------------
    # Settings & debug dialogs (placeholders)
    # ---------------------------------------------------------------------
    def open_settings(self):
        pass

    def open_debug_log(self):
        if self.debug_dialog is None:
            from .debug_dialog import DebugLogDialog
            self.debug_dialog = DebugLogDialog(self)
        self.debug_dialog.show()
        self.debug_dialog.raise_()