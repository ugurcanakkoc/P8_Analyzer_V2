# MainWindow implementation for P8 Analyzer

import os
import pymupdf
from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QToolBar, QAction,
    QDockWidget, QTextEdit, QLabel, QMessageBox, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView
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

        # --- DOCKS ---
        
        # 1. Log Panel (Right)
        dock_log = QDockWidget("Loglar", self)
        dock_log.setAllowedAreas(Qt.RightDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        dock_log.setWidget(self.log_text)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_log)

        # 2. Connection Table (Bottom)
        dock_table = QDockWidget("Bağlantı Listesi", self)
        dock_table.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(7)
        self.conn_table.setHorizontalHeaderLabels([
            "Source Tag", "Source Pin", 
            "Target Tag", "Target Pin", 
            "Wire Color", "Cross-Section", "Cable Tag"
        ])
        # Tablo ayarları
        header = self.conn_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.conn_table.setAlternatingRowColors(True)
        
        dock_table.setWidget(self.conn_table)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_table)

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
            
            # Tabloyu temizle
            self.conn_table.setRowCount(0)
            
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

        # ---- BUSBAR DETECTION ----
        busbar_count = 0
        self.log("\n--- BUSBAR ANALİZİ ---")
        
        # Sayfa boyutlarını al (tahmini veya doc'dan)
        page_width = 0
        if self.doc:
            page = self.doc.load_page(self.current_page - 1)
            page_width = page.rect.width

        busbar_threshold_ratio = 0.3 # Sayfanın %30'undan uzunsa busbar kabul et
        
        # Label Matcher'ı hazırla
        matcher = None
        try:
            matcher = LabelMatcher(self.doc.load_page(self.current_page - 1))
        except Exception as e:
            self.log(f"Label Matcher başlatılamadı: {e}")

        for i, group in enumerate(self.current_result.structural_groups):
            # Grup bounding box'ını hesapla (eğer yoksa)
            if not group.bounding_box:
                group.calculate_bounding_box()
            
            bbox = group.bounding_box
            width = bbox['max_x'] - bbox['min_x']
            height = bbox['max_y'] - bbox['min_y']
            
            is_busbar = False
            
            # Sadece Yatay Busbar Kontrolü
            if width > page_width * busbar_threshold_ratio and width > height * 2:
                is_busbar = True
            
            if is_busbar:
                busbar_count += 1
                net_id = f"NET-{i+1:03d}"
                self.log(f"⚡ Olası Yatay Busbar Bulundu: {net_id} (Uzunluk: {width:.1f})")
                
                # Busbar başlangıç noktasında (sol taraf) ve üstünde etiket ara
                if matcher:
                    # En sol noktayı bul (start_x)
                    start_x = bbox['min_x']
                    # Y koordinatı (yaklaşık olarak min_y veya ortalama y)
                    start_y = bbox['min_y'] 
                    
                    # Arama kutusu: Başlangıçtan sağa doğru 150 birim, yukarı doğru 40 birim
                    # (x0, y0, x1, y1)
                    search_rect = (
                        start_x - 10,       # Biraz sol payı
                        start_y - 40,       # 40 birim yukarı
                        start_x + 150,      # 150 birim sağa
                        start_y + 5         # Biraz aşağı payı (çizgi kalınlığı vs.)
                    )
                    
                    # Bu alan içindeki etiketleri bul
                    labels = matcher.find_labels_in_rect(search_rect)
                    
                    if labels:
                        # Bulunan etiketleri birleştir
                        label_str = ", ".join(labels)
                        self.log(f"   🏷️ Busbar Etiketi: {label_str}")
                        connections.setdefault(net_id, []).extend([f"BUSBAR:{lbl}" for lbl in labels])

        self.log(f"Toplam {busbar_count} adet potansiyel Busbar tespit edildi.")
        self.log("----------------------")

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

        # ---- LabelMatcher fallback (Diğer hatlar için) ----
        if matcher:
            try:
                for i, group in enumerate(self.current_result.structural_groups):
                    net_id = f"NET-{i+1:03d}"
                    
                    endpoints = []
                    for elem in group.elements:
                        endpoints.append((elem.start_point.x, elem.start_point.y))
                        endpoints.append((elem.end_point.x, elem.end_point.y))
                    if endpoints:
                        labels = matcher.find_labels_for_net(endpoints, all_components)
                        if labels:
                            current_conns = connections.get(net_id, [])
                            for lbl in labels:
                                lbl_str = f"LABEL:{lbl}"
                                busbar_lbl_str = f"BUSBAR:{lbl}"
                                if lbl_str not in current_conns and busbar_lbl_str not in current_conns:
                                     connections.setdefault(net_id, []).append(lbl_str)
            except Exception as e:
                self.log(f"Label Matcher hatası: {e}")

        # Reporting & Table Population
        self.log("\n====== BAĞLANTI RAPORU ======")
        self.conn_table.setRowCount(0) # Tabloyu temizle
        
        found_any = False
        for net_id in sorted(connections.keys()):
            comp_ids = connections[net_id]
            if comp_ids:
                found_any = True
                self.log(f"🔹 {net_id} Hattı:")
                
                # Loglama
                for comp_id in comp_ids:
                    icon = "🔌"
                    if "BOX" in comp_id: icon = "📦"
                    elif "LABEL" in comp_id: icon = "🏷️"
                    elif "BUSBAR" in comp_id: icon = "⚡"
                    self.log(f"   └─ {icon} {comp_id}")
                
                # Tabloya Ekleme (Basit Mantık: İlk eleman Source, diğerleri Target)
                # Daha gelişmiş mantık için pin/klemens ayrımı yapılabilir.
                # Şimdilik listedeki her bir ikili kombinasyonu veya zinciri ekleyelim.
                # Örn: A, B, C -> A-B, B-C gibi veya A-B, A-C.
                # Basitlik için: İlk elemanı kaynak al, diğerlerini hedef yap.
                
                # Listeyi temizle ve sırala
                unique_comps = sorted(list(set(comp_ids)))
                if len(unique_comps) >= 2:
                    source_full = unique_comps[0]
                    
                    for target_full in unique_comps[1:]:
                        self._add_table_row(source_full, target_full)

        if not found_any:
            self.log("❌ Hiçbir bağlantı bulunamadı.")
            self.log("İpucu: Klemensler veya kutular hatların üzerine gelmiyor olabilir.")

    def _add_table_row(self, source_full, target_full):
        """Tabloya yeni bir satır ekler."""
        row = self.conn_table.rowCount()
        self.conn_table.insertRow(row)
        
        # Parse Source (Örn: BOX-1:P24.i1 -> Tag: BOX-1, Pin: P24.i1)
        s_tag, s_pin = self._parse_comp_id(source_full)
        t_tag, t_pin = self._parse_comp_id(target_full)
        
        self.conn_table.setItem(row, 0, QTableWidgetItem(s_tag))
        self.conn_table.setItem(row, 1, QTableWidgetItem(s_pin))
        self.conn_table.setItem(row, 2, QTableWidgetItem(t_tag))
        self.conn_table.setItem(row, 3, QTableWidgetItem(t_pin))
        
        # Diğer kolonlar şimdilik boş
        self.conn_table.setItem(row, 4, QTableWidgetItem("")) # Color
        self.conn_table.setItem(row, 5, QTableWidgetItem("")) # Cross-Section
        self.conn_table.setItem(row, 6, QTableWidgetItem("")) # Cable Tag

    def _parse_comp_id(self, comp_id):
        """
        'BOX-1:P24' -> ('BOX-1', 'P24')
        'LABEL:P24.i1' -> ('', 'P24.i1')
        'BUSBAR:L1' -> ('BUSBAR', 'L1')
        """
        if ":" in comp_id:
            parts = comp_id.split(":", 1)
            tag = parts[0]
            pin = parts[1]
            
            # Özel durumlar
            if tag == "LABEL": tag = "Wire"
            if tag == "BUSBAR": tag = "Busbar"
            
            return tag, pin
        else:
            return comp_id, ""

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
