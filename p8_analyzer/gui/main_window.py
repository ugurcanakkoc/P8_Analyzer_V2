# MainWindow implementation for P8 Analyzer

import os
import json
from pathlib import Path
from datetime import datetime
import pymupdf
from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QToolBar, QAction,
    QDockWidget, QTextEdit, QLabel, QMessageBox, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent

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

    def init_ui(self):
        self.viewer = InteractiveGraphicsView()
        self.setCentralWidget(self.viewer)

        toolbar = QToolBar(t("toolbar_name"))
        self.addToolBar(toolbar)

        act_open = QAction(f"📂 {t('btn_open_pdf')}", self)
        act_open.triggered.connect(self.browse_pdf)
        toolbar.addAction(act_open)
        toolbar.addSeparator()

        self.act_prev = QAction(f"◀ {t('btn_prev')}", self)
        self.act_prev.triggered.connect(self.prev_page)
        self.act_prev.setEnabled(False)
        toolbar.addAction(self.act_prev)

        self.lbl_page = QLabel(f" {t('page_label_empty')} ")
        toolbar.addWidget(self.lbl_page)

        self.act_next = QAction(f"{t('btn_next')} ▶", self)
        self.act_next.triggered.connect(self.next_page)
        self.act_next.setEnabled(False)
        toolbar.addAction(self.act_next)
        toolbar.addSeparator()

        self.act_analyze = QAction(f"⚡ {t('btn_analyze')}", self)
        self.act_analyze.triggered.connect(self.start_analysis)
        self.act_analyze.setEnabled(False)
        toolbar.addAction(self.act_analyze)
        toolbar.addSeparator()

        self.act_ocr_test = QAction(f"👁️ {t('btn_ocr_test')}", self)
        self.act_ocr_test.triggered.connect(self.run_ocr_test)
        self.act_ocr_test.setEnabled(False)
        toolbar.addAction(self.act_ocr_test)

        self.act_nav = QAction(f"✋ {t('btn_navigate')}", self)
        self.act_nav.setCheckable(True)
        self.act_nav.setChecked(True)
        self.act_nav.triggered.connect(lambda: self.set_mode("NAVIGATE"))
        toolbar.addAction(self.act_nav)

        self.act_draw = QAction(f"🟥 {t('btn_draw_box')}", self)
        self.act_draw.setCheckable(True)
        self.act_draw.triggered.connect(lambda: self.set_mode("DRAW"))
        toolbar.addAction(self.act_draw)

        self.act_check = QAction(f"🔗 {t('btn_connection_check')}", self)
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
        self.conn_table.setAlternatingRowColors(True)
        dock_table.setWidget(self.conn_table)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_table)

        self.status_bar = self.statusBar()

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

    def browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, t("msg_select_pdf"), "", "PDF (*.pdf)")
        if path and self.load_pdf_file(path):
            self.current_page = 1
            self.load_current_page()

    def load_pdf_file(self, path):
        try:
            if self.doc: self.doc.close()
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
            return True
        except Exception as e:
            QMessageBox.critical(self, t("msg_error"), str(e))
            return False

    def load_current_page(self):
        if not self.doc: return
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

    def prev_page(self):
        if self.schematic_filter_active and self.schematic_pages:
            # Navigate to previous schematic page
            current_idx = self.schematic_pages.index(self.current_page) if self.current_page in self.schematic_pages else 0
            if current_idx > 0:
                self.current_page = self.schematic_pages[current_idx - 1]
                self.load_current_page()
        elif self.current_page > 1:
            self.current_page -= 1
            self.load_current_page()

    def next_page(self):
        if self.schematic_filter_active and self.schematic_pages:
            # Navigate to next schematic page
            current_idx = self.schematic_pages.index(self.current_page) if self.current_page in self.schematic_pages else -1
            if current_idx < len(self.schematic_pages) - 1:
                self.current_page = self.schematic_pages[current_idx + 1]
                self.load_current_page()
        elif self.current_page < self.total_pages:
            self.current_page += 1
            self.load_current_page()

    def set_mode(self, mode):
        self.viewer.set_mode(mode)
        self.act_nav.setChecked(mode == "NAVIGATE")
        self.act_draw.setChecked(mode == "DRAW")
        self.status_bar.showMessage(t("msg_mode", mode=mode))

    def start_analysis(self):
        if not self.doc: return
        self.log(t("msg_analyzing", page=self.current_page))
        self.act_analyze.setEnabled(False)
        self.worker = AnalysisWorker(self.doc.name, self.current_page)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_analysis_finished(self, result):
        self.act_analyze.setEnabled(True)
        self.current_result = result
        # Pass page for PIL-based cluster visualization
        page = self.doc.load_page(self.current_page - 1) if self.doc else None
        self.viewer.draw_analysis_result(result, page=page)
        self.act_check.setEnabled(True)
        self.act_ocr_test.setEnabled(True)
        self.log(t("msg_analysis_complete", count=len(result.structural_groups)))
        self.run_connection_check()

    def on_error(self, msg):
        self.log(msg)
        self.act_analyze.setEnabled(True)

    def run_ocr_test(self):
        if not hasattr(self, "current_result") or not self.doc: return
        self.ocr_worker = OCRComparisonWorker(self.doc.name, self.current_page, self.current_result)
        self.ocr_worker.log_signal.connect(self.log)
        self.ocr_worker.start()

    def run_connection_check(self):
        manual_boxes = self.viewer.get_drawn_components()
        if not hasattr(self, "current_result"): return

        matcher = None
        try:
            matcher = LabelMatcher(self.doc.load_page(self.current_page - 1))
        except: pass

        if not self.text_engine:
            self.text_engine = HybridTextEngine(["en"])
            if self.doc: self.text_engine.load_page(self.doc.load_page(self.current_page - 1))

        if self.text_engine and manual_boxes:
            ComponentNamer(self.text_engine).name_boxes(manual_boxes, self.log)

        # 1. Klemens Dönüşümü
        terminal_components = []
        used_term_ids = {} # { "label": count }

        if hasattr(self.current_result, "terminals") and self.current_result.terminals:
            for term in self.current_result.terminals:
                cx, cy = term["center"]
                base_label = term.get("full_label") or term.get("label") or f"TERM"
                
                # Unique ID generation
                if base_label in used_term_ids:
                    used_term_ids[base_label] += 1
                    term_id = f"{base_label} ({used_term_ids[base_label]})"
                else:
                    used_term_ids[base_label] = 1
                    term_id = base_label

                comp = CircuitComponent(
                    id=term_id, label="Terminal",
                    bbox={"min_x": cx-2, "min_y": cy-2, "max_x": cx+2, "max_y": cy+2}
                )
                terminal_components.append(comp)

        # 2. Bağlantı Kontrolü (NET-XXX ID'leri ile)
        all_comps = manual_boxes + terminal_components
        connections = check_intersections(all_comps, self.current_result)

        # 3. BUSBAR TESPİTİ ve NET ID GÜNCELLEME
        # Burası değişti: Busbar adı bulunursa, NET-XXX silinir, yerine Busbar adı (örn: P24) geçer.
        if matcher:
            busbar_map = BusbarFinder(matcher).find_busbars(
                self.current_result.structural_groups, 
                self.doc[0].rect.width if self.doc else 0,
                manual_boxes, self.viewer
            )
            
            # Map'teki her busbar için connections sözlüğündeki anahtarı değiştir
            # Eski anahtar: 'NET-005', Yeni anahtar: 'P24'
            new_connections = {}
            for net_id, items in connections.items():
                if net_id in busbar_map:
                    new_id = busbar_map[net_id] # Örn: "P24"
                    # Mevcut listeye busbar adını da ekle (referans olması için)
                    items.insert(0, f"[BUSBAR: {new_id}]")
                    
                    # Eğer bu isimde bir hat zaten varsa birleştir, yoksa oluştur
                    if new_id in new_connections:
                        new_connections[new_id].extend(items)
                    else:
                        new_connections[new_id] = items
                else:
                    new_connections[net_id] = items
            
            connections = new_connections

        # 4. Pin Finder (Kutu İçi Pinler)
        if manual_boxes:
            pin_finder = PinFinder(self.app_settings)
            for i, group in enumerate(self.current_result.structural_groups):
                # Orijinal ID'yi bulmamız lazım çünkü group index değişmedi
                original_net_id = f"NET-{i+1:03d}"
                
                # Bu orijinal ID şu an connections içinde "P24" olmuş olabilir.
                # Bunu bulmak için busbar_map'e bakabiliriz veya tersine arama yapabiliriz.
                # Kolay yöntem: Bulunan pinleri, current target ID'ye eklemek.
                
                target_key = original_net_id
                if matcher and original_net_id in busbar_map:
                    target_key = busbar_map[original_net_id]

                found_pins = pin_finder.find_pins_for_group(group, manual_boxes, self.text_engine)
                if found_pins:
                    pins_formatted = [p["full_label"] for p in found_pins]
                    connections.setdefault(target_key, []).extend(pins_formatted)

        # Raporlama
        self.log(f"\n{t('msg_connection_report')}")
        self.conn_table.setRowCount(0) 
        
        # Sıralama: Önce Busbarlar (Alfabetik olmayan NET-XXX ler sona)
        sorted_keys = sorted(connections.keys(), key=lambda k: (k.startswith("NET"), k))

        for net_id in sorted_keys:
            raw_ids = connections[net_id]
            unique_ids = list(dict.fromkeys(raw_ids)) # Tekilleştir
            
            # 1. Busbar ve Bileşenleri Ayır
            busbar_name = None
            components = []
            
            for uid in unique_ids:
                if uid.startswith("[BUSBAR:"):
                    # [BUSBAR: P24] -> P24
                    busbar_name = uid.split(":")[1].strip(" ]")
                else:
                    components.append(uid)
            
            # 2. Pin Kontrolü (Pin'i olmayanları ayıkla ve logla)
            valid_components = []
            for comp_id in components:
                if ":" in comp_id:
                    valid_components.append(comp_id)
                else:
                    # Pin yoksa loga düş, tabloya ekleme
                    self.log(f"⚠️ {t('msg_warning_no_pin', comp=comp_id, net=net_id)}")

            if not valid_components:
                continue

            # 3. Kaynak - Hedef Belirleme ve Tabloya Ekleme
            if busbar_name:
                # Senaryo A: Busbar Kaynak
                # Busbar -> Tüm Valid Componentler
                for target in valid_components:
                    self._add_table_row(busbar_name, target)
                    self.log(f"⚡ {busbar_name} ==> {target}")
            else:
                # Senaryo B: Normal Bağlantı (Net)
                # Klemens var mı? (-X ile başlayanlar)
                terminals = [c for c in valid_components if c.startswith("-X")]
                devices = [c for c in valid_components if not c.startswith("-X")]
                
                # Eğer hiç geçerli bileşen yoksa atla
                if not terminals and not devices:
                    continue
                    
                # Kaynak Belirle
                source = None
                targets = []
                
                if terminals:
                    # Klemens varsa, ilk klemens kaynak olur
                    source = terminals[0]
                    # Geriye kalanlar hedef (Diğer klemensler + cihazlar)
                    targets = terminals[1:] + devices
                else:
                    # Sadece cihazlar varsa, ilki kaynak
                    source = devices[0]
                    targets = devices[1:]
                
                # Tabloya Ekle
                for target in targets:
                    self._add_table_row(source, target)
                    self.log(f"🔹 {source} --> {target}")

        if self.conn_table.rowCount() == 0:
            self.log(f"❌ {t('msg_no_valid_connections')}")

    def _add_table_row(self, source, target):
        row = self.conn_table.rowCount()
        self.conn_table.insertRow(row)
        
        s_tag, s_pin = self._parse_comp_id(source)
        t_tag, t_pin = self._parse_comp_id(target)
        
        self.conn_table.setItem(row, 0, QTableWidgetItem(s_tag))
        self.conn_table.setItem(row, 1, QTableWidgetItem(s_pin))
        self.conn_table.setItem(row, 2, QTableWidgetItem(t_tag))
        self.conn_table.setItem(row, 3, QTableWidgetItem(t_pin))

    def _parse_comp_id(self, text):
        if ":" in text:
            parts = text.split(":", 1)
            return parts[0], parts[1]
        return text, ""

    def log(self, msg):
        self.log_text.append(msg)

    # ========== PAGE CLASSIFICATION METHODS ==========

    def toggle_classification_mode(self):
        """Toggle classification mode on/off."""
        self.classification_mode = self.act_classify.isChecked()
        if self.classification_mode:
            self.log(t("msg_classification_mode_on"))
            self.status_bar.showMessage(t("msg_classification_mode_on"))
        else:
            self.log(t("msg_classification_mode_off"))
            self.status_bar.showMessage(t("msg_classification_mode_off"))
        self.update_classification_status()

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

    def save_classifications(self):
        """Save classifications to JSON and export schematic pages as images."""
        if not self.page_classifications:
            return

        if not self.pdf_path:
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
                # Render at 150 DPI for training
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

    def toggle_schematic_filter(self):
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

    def scan_schematic_pages(self):
        """Scan all pages using the page classifier model (background thread)."""
        if not self.doc:
            return

        # Check model exists
        model_path = Path(__file__).parent.parent / "models" / "page_classifier.pt"
        if not model_path.exists():
            self.log(t("msg_model_not_found"))
            QMessageBox.warning(self, t("msg_error"), t("msg_model_not_found"))
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

    def _on_classifier_progress(self, current: int, total: int):
        """Update progress dialog during classification."""
        if hasattr(self, 'classifier_progress') and self.classifier_progress:
            self.classifier_progress.setValue(current)
            self.classifier_progress.setLabelText(f"Scanning page {current} / {total}...")

    def _on_page_classified(self, page_num: int, class_name: str, confidence: float):
        """Handle individual page classification result."""
        # Optional: could log each classification if verbose mode desired
        pass

    def _on_classifier_finished(self, schematic_pages: list):
        """Handle classification completion."""
        # Close progress dialog
        if hasattr(self, 'classifier_progress') and self.classifier_progress:
            self.classifier_progress.close()
            self.classifier_progress = None

        self.schematic_pages = schematic_pages
        self.log(t("msg_filter_complete", count=len(schematic_pages), total=self.total_pages))
        self.status_bar.showMessage(t("msg_filter_complete", count=len(schematic_pages), total=self.total_pages))

        # Now activate the filter if we found schematics
        if schematic_pages:
            self.schematic_filter_active = True
            self.log(t("msg_filter_on", count=len(schematic_pages)))

            # Jump to first schematic page if current page is not a schematic
            if self.current_page not in schematic_pages:
                self.current_page = schematic_pages[0]

            self.load_current_page()
        else:
            # No schematics found, disable filter
            self.act_schematic_filter.setChecked(False)
            QMessageBox.information(self, t("btn_schematic_filter"),
                                   f"No schematic pages found in {self.total_pages} pages.")

    def _on_classifier_error(self, error_msg: str):
        """Handle classification errors."""
        self.log(f"[ERROR] {error_msg}")

    def _on_classifier_cancelled(self):
        """Handle user cancellation of classification."""
        if hasattr(self, 'classifier_worker') and self.classifier_worker:
            self.classifier_worker.cancel()
            self.classifier_worker.wait()
        self.log("Classification cancelled by user")
        self.act_schematic_filter.setChecked(False)