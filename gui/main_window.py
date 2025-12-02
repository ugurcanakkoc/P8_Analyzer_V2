import os
import pymupdf
from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QToolBar, QAction,
    QDockWidget, QTextEdit, QLabel, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt

# Local modules
from .viewer import InteractiveGraphicsView
from .worker import AnalysisWorker
from .ocr_worker import OCRComparisonWorker
from .circuit_logic import check_intersections, CircuitComponent
from src.label_matcher import LabelMatcher
from src.pin_finder import PinFinder
from src.text_engine import HybridTextEngine
from src.busbar_finder import BusbarFinder
from src.component_namer import ComponentNamer

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
        self.text_engine = None 
        self.current_result = None

        self.init_ui()
        self.load_default_file()

    def init_ui(self):
        self.viewer = InteractiveGraphicsView()
        self.setCentralWidget(self.viewer)

        toolbar = QToolBar("Araçlar")
        self.addToolBar(toolbar)

        act_open = QAction("📂 PDF Aç", self)
        act_open.triggered.connect(self.browse_pdf)
        toolbar.addAction(act_open)
        toolbar.addSeparator()

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

        self.act_analyze = QAction("⚡ Analiz Et", self)
        self.act_analyze.triggered.connect(self.start_analysis)
        self.act_analyze.setEnabled(False)
        toolbar.addAction(self.act_analyze)
        toolbar.addSeparator()

        self.act_ocr_test = QAction("👁️ OCR vs PDF", self)
        self.act_ocr_test.triggered.connect(self.run_ocr_test)
        self.act_ocr_test.setEnabled(False)
        toolbar.addAction(self.act_ocr_test)

        self.act_nav = QAction("✋ Gezin", self)
        self.act_nav.setCheckable(True)
        self.act_nav.setChecked(True)
        self.act_nav.triggered.connect(lambda: self.set_mode("NAVIGATE"))
        toolbar.addAction(self.act_nav)

        self.act_draw = QAction("🟥 Kutu Çiz", self)
        self.act_draw.setCheckable(True)
        self.act_draw.triggered.connect(lambda: self.set_mode("DRAW"))
        toolbar.addAction(self.act_draw)

        self.act_check = QAction("🔗 Bağlantı Kontrol", self)
        self.act_check.triggered.connect(self.run_connection_check)
        self.act_check.setEnabled(False)
        toolbar.addAction(self.act_check)

        # Docks
        dock_log = QDockWidget("Loglar", self)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        dock_log.setWidget(self.log_text)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_log)

        dock_table = QDockWidget("Bağlantı Listesi", self)
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(4)
        self.conn_table.setHorizontalHeaderLabels(["Hat/Bus", "Pin/Uç", "Hedef", "Pin"])
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
            self.log(f"Otomatik yükleme: {default_path}")
            if self.load_pdf_file(default_path):
                target_page = 27
                if target_page <= self.total_pages:
                    self.current_page = target_page
                    self.load_current_page()
        else:
            self.log(f"'{default_path}' bulunamadı.")

    def browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF Seç", "", "PDF (*.pdf)")
        if path and self.load_pdf_file(path):
            self.current_page = 1
            self.load_current_page()

    def load_pdf_file(self, path):
        try:
            if self.doc: self.doc.close()
            self.doc = pymupdf.open(path)
            self.total_pages = len(self.doc)
            self.text_engine = None 
            return True
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
            return False

    def load_current_page(self):
        if not self.doc: return
        try:
            page = self.doc.load_page(self.current_page - 1)
            self.viewer.set_background_image(page)
            self.lbl_page.setText(f" Sayfa: {self.current_page} / {self.total_pages} ")
            self.act_prev.setEnabled(self.current_page > 1)
            self.act_next.setEnabled(self.current_page < self.total_pages)
            self.act_analyze.setEnabled(True)
            self.act_check.setEnabled(False)
            self.act_ocr_test.setEnabled(False)
            self.current_result = None
            self.conn_table.setRowCount(0)
        except Exception as e:
            self.log(f"Sayfa hatası: {e}")

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_current_page()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_current_page()

    def set_mode(self, mode):
        self.viewer.set_mode(mode)
        self.act_nav.setChecked(mode == "NAVIGATE")
        self.act_draw.setChecked(mode == "DRAW")
        self.status_bar.showMessage(f"Mod: {mode}")

    def start_analysis(self):
        if not self.doc: return
        self.log(f"Sayfa {self.current_page} analiz ediliyor...")
        self.act_analyze.setEnabled(False)
        self.worker = AnalysisWorker(self.doc.name, self.current_page)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_analysis_finished(self, result):
        self.act_analyze.setEnabled(True)
        self.current_result = result
        self.viewer.draw_analysis_result(result)
        self.act_check.setEnabled(True)
        self.act_ocr_test.setEnabled(True)
        self.log(f"Analiz Bitti. {len(result.structural_groups)} hat bulundu.")
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

        if matcher and manual_boxes:
            ComponentNamer(matcher).name_boxes(manual_boxes, self.log)

        # 1. Klemens Dönüşümü
        terminal_components = []
        if hasattr(self.current_result, "terminals") and self.current_result.terminals:
            for term in self.current_result.terminals:
                cx, cy = term["center"]
                term_label = term.get("full_label") or term.get("label") or f"TERM"
                comp = CircuitComponent(
                    id=term_label, label="Terminal",
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
        self.log("\n====== BAĞLANTI RAPORU ======")
        self.conn_table.setRowCount(0) 
        
        # Sıralama: Önce Busbarlar (Alfabetik olmayan NET-XXX ler sona)
        sorted_keys = sorted(connections.keys(), key=lambda k: (k.startswith("NET"), k))

        for net_id in sorted_keys:
            raw_ids = connections[net_id]
            unique_ids = list(dict.fromkeys(raw_ids)) # Tekilleştir
            
            # Eğer listede sadece "[BUSBAR: P24]" gibi tek eleman varsa gösterme (bağlantı yok demektir)
            if len(unique_ids) < 2 and not (len(unique_ids)==1 and "BUSBAR" in unique_ids[0]):
                 # Ama Busbar ise ve tek başına duruyorsa da görmek isteyebiliriz.
                 # Yine de en az 2 nokta arası bağlantı arıyoruz.
                 pass

            if unique_ids:
                icon = "⚡" if not net_id.startswith("NET-") else "🔹"
                self.log(f"{icon} {net_id} Hattı: {', '.join(unique_ids)}")
                
                # Tabloya Ekle (Source -> Target)
                # Source olarak Hattın adını (net_id) kullanabiliriz veya ilk bileşeni
                if len(unique_ids) >= 1:
                    src = net_id # Hat adı kaynak olsun (örn: P24)
                    for target in unique_ids:
                        if "BUSBAR" in target: continue # Kendini referans verme
                        self._add_table_row(src, target)

        if not connections:
            self.log("❌ Bağlantı bulunamadı.")

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