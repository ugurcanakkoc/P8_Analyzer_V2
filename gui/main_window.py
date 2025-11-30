import os
import pymupdf
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QToolBar, QAction, 
                             QDockWidget, QTextEdit, QLabel, QMessageBox, QWidget, QVBoxLayout)
from PyQt5.QtCore import Qt

# Kendi modüllerimiz
from .viewer import InteractiveGraphicsView
from .worker import AnalysisWorker
from .circuit_logic import check_intersections
from .ocr_worker import OCRComparisonWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UVP - Professional Vector Analyzer")
        self.resize(1200, 800)
        
        # Durum Değişkenleri
        self.doc = None
        self.current_page = 1
        self.total_pages = 0
        
        self.init_ui()
        
        # --- OTOMATİK BAŞLATMA ---
        # Program açılınca otomatik olarak data/ornek.pdf'i yüklemeyi dene
        self.load_default_file()

    def init_ui(self):
        # 1. Viewer (Canvas)
        self.viewer = InteractiveGraphicsView()
        self.setCentralWidget(self.viewer)
        
        # 2. Toolbar
        toolbar = QToolBar("Araçlar")
        self.addToolBar(toolbar)
        
        # Dosya Aç
        act_open = QAction("📂 PDF Aç", self)
        act_open.triggered.connect(self.browse_pdf) # İsmini browse_pdf yaptık
        toolbar.addAction(act_open)
        
        toolbar.addSeparator()
        
        # Navigasyon
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
        
        # Analiz Butonu
        self.act_analyze = QAction("⚡ Analiz Et", self)
        self.act_analyze.triggered.connect(self.start_analysis)
        self.act_analyze.setEnabled(False)
        toolbar.addAction(self.act_analyze)
        
        toolbar.addSeparator()
        # OCR Butonu
        self.act_ocr_test = QAction("👁️ OCR vs PDF", self)
        self.act_ocr_test.triggered.connect(self.run_ocr_test)
        self.act_ocr_test.setEnabled(False) # Analizden sonra açılacak
        toolbar.addAction(self.act_ocr_test)
        # Mod Butonları
        self.act_nav = QAction("✋ Gezin", self)
        self.act_nav.setCheckable(True); self.act_nav.setChecked(True)
        self.act_nav.triggered.connect(lambda: self.set_mode("NAVIGATE"))
        toolbar.addAction(self.act_nav)
        
        self.act_draw = QAction("🟥 Kutu Çiz", self)
        self.act_draw.setCheckable(True)
        self.act_draw.triggered.connect(lambda: self.set_mode("DRAW"))
        toolbar.addAction(self.act_draw)
        
        # Bağlantı Kontrol Butonu
        self.act_check = QAction("🔗 Bağlantı Kontrol", self)
        self.act_check.triggered.connect(self.run_connection_check)
        self.act_check.setEnabled(False) 
        toolbar.addAction(self.act_check)
        
        # 3. Log Paneli
        dock = QDockWidget("Loglar", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        dock.setWidget(self.log_text)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        
        # 4. Status Bar
        self.status_bar = self.statusBar()

    def load_default_file(self):
        """Otomatik olarak data/ornek.pdf dosyasını ve 18. sayfayı açar."""
        # Proje kök dizinini bul
        base_dir = os.getcwd()
        default_path = os.path.join(base_dir, "data", "ornek.pdf")
        
        if os.path.exists(default_path):
            self.log(f"Otomatik yükleme: {default_path}")
            if self.load_pdf_file(default_path):
                # Dosya başarıyla açıldıysa sayfa 18'e git
                target_page = 25
                if target_page <= self.total_pages:
                    self.current_page = target_page
                    self.load_current_page()
                else:
                    self.log(f"Uyarı: PDF {self.total_pages} sayfa, 18. sayfa açılamadı.")
        else:
            self.log("Bilgi: 'data/ornek.pdf' bulunamadı, boş açılıyor.")

    def browse_pdf(self):
        """Kullanıcıya dosya seçtirme diyaloğu."""
        path, _ = QFileDialog.getOpenFileName(self, "PDF Seç", "", "PDF (*.pdf)")
        if path:
            if self.load_pdf_file(path):
                self.current_page = 1
                self.load_current_page()

    def load_pdf_file(self, path):
        """Verilen path'teki PDF'i açar (Mantıksal yükleme)."""
        try:
            self.doc = pymupdf.open(path)
            self.total_pages = len(self.doc)
            self.log(f"PDF Yüklendi: {os.path.basename(path)} ({self.total_pages} sayfa)")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF açılamadı:\n{str(e)}")
            return False

    def load_current_page(self):
        """Mevcut self.current_page'i ekrana ve viewer'a yükler."""
        if not self.doc: return
        
        try:
            # 1. Viewer'a resmi yükle (Arkaplanı temizler)
            # PyMuPDF sayfa indexi 0'dan başlar, biz 1'den sayıyoruz.
            page_index = self.current_page - 1
            page = self.doc.load_page(page_index)
            self.viewer.set_background_image(page)
            
            # 2. UI Durumlarını Güncelle
            self.status_bar.showMessage(f"Sayfa {self.current_page} yüklendi.")
            self.lbl_page.setText(f" Sayfa: {self.current_page} / {self.total_pages} ")
            
            # Navigasyon butonlarını kontrol et
            self.act_prev.setEnabled(self.current_page > 1)
            self.act_next.setEnabled(self.current_page < self.total_pages)
            
            # Analiz butonunu aktif et
            self.act_analyze.setEnabled(True)
            
            # Eski analiz sonuçlarını ve bağlantı butonunu sıfırla
            self.act_check.setEnabled(False)
            if hasattr(self, 'current_result'): 
                del self.current_result
            
            # Kutu çizme modundaysa NAVIGATE'e geri alabiliriz (isteğe bağlı)
            # self.set_mode("NAVIGATE") 

        except Exception as e:
            self.log(f"Sayfa yükleme hatası: {e}")

    def prev_page(self):
        """Önceki sayfaya geçer."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_current_page()

    def next_page(self):
        """Sonraki sayfaya geçer."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_current_page()

    def set_mode(self, mode):
        """Modlar arası geçiş yapar."""
        if mode == "NAVIGATE":
            self.act_nav.setChecked(True); self.act_draw.setChecked(False)
            self.viewer.set_mode("NAVIGATE")
import os
import pymupdf
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QToolBar, QAction, 
                             QDockWidget, QTextEdit, QLabel, QMessageBox, QWidget, QVBoxLayout)
from PyQt5.QtCore import Qt

# Kendi modüllerimiz
from .viewer import InteractiveGraphicsView
from .worker import AnalysisWorker
from .circuit_logic import check_intersections
from .ocr_worker import OCRComparisonWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UVP - Professional Vector Analyzer")
        self.resize(1200, 800)
        
        # Durum Değişkenleri
        self.doc = None
        self.current_page = 1
        self.total_pages = 0
        
        self.init_ui()
        
        # --- OTOMATİK BAŞLATMA ---
        # Program açılınca otomatik olarak data/ornek.pdf'i yüklemeyi dene
        self.load_default_file()

    def init_ui(self):
        # 1. Viewer (Canvas)
        self.viewer = InteractiveGraphicsView()
        self.setCentralWidget(self.viewer)
        
        # 2. Toolbar
        toolbar = QToolBar("Araçlar")
        self.addToolBar(toolbar)
        
        # Dosya Aç
        act_open = QAction("📂 PDF Aç", self)
        act_open.triggered.connect(self.browse_pdf) # İsmini browse_pdf yaptık
        toolbar.addAction(act_open)
        
        toolbar.addSeparator()
        
        # Navigasyon
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
        
        # Analiz Butonu
        self.act_analyze = QAction("⚡ Analiz Et", self)
        self.act_analyze.triggered.connect(self.start_analysis)
        self.act_analyze.setEnabled(False)
        toolbar.addAction(self.act_analyze)
        
        toolbar.addSeparator()
        # OCR Butonu
        self.act_ocr_test = QAction("👁️ OCR vs PDF", self)
        self.act_ocr_test.triggered.connect(self.run_ocr_test)
        self.act_ocr_test.setEnabled(False) # Analizden sonra açılacak
        toolbar.addAction(self.act_ocr_test)
        # Mod Butonları
        self.act_nav = QAction("✋ Gezin", self)
        self.act_nav.setCheckable(True); self.act_nav.setChecked(True)
        self.act_nav.triggered.connect(lambda: self.set_mode("NAVIGATE"))
        toolbar.addAction(self.act_nav)
        
        self.act_draw = QAction("🟥 Kutu Çiz", self)
        self.act_draw.setCheckable(True)
        self.act_draw.triggered.connect(lambda: self.set_mode("DRAW"))
        toolbar.addAction(self.act_draw)
        
        # Bağlantı Kontrol Butonu
        self.act_check = QAction("🔗 Bağlantı Kontrol", self)
        self.act_check.triggered.connect(self.run_connection_check)
        self.act_check.setEnabled(False) 
        toolbar.addAction(self.act_check)
        
        # 3. Log Paneli
        dock = QDockWidget("Loglar", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        dock.setWidget(self.log_text)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        
        # 4. Status Bar
        self.status_bar = self.statusBar()

    def load_default_file(self):
        """Otomatik olarak data/ornek.pdf dosyasını ve 18. sayfayı açar."""
        # Proje kök dizinini bul
        base_dir = os.getcwd()
        default_path = os.path.join(base_dir, "data", "ornek.pdf")
        
        if os.path.exists(default_path):
            self.log(f"Otomatik yükleme: {default_path}")
            if self.load_pdf_file(default_path):
                # Dosya başarıyla açıldıysa sayfa 18'e git
                target_page = 18
                if target_page <= self.total_pages:
                    self.current_page = target_page
                    self.load_current_page()
                else:
                    self.log(f"Uyarı: PDF {self.total_pages} sayfa, 18. sayfa açılamadı.")
        else:
            self.log("Bilgi: 'data/ornek.pdf' bulunamadı, boş açılıyor.")

    def browse_pdf(self):
        """Kullanıcıya dosya seçtirme diyaloğu."""
        path, _ = QFileDialog.getOpenFileName(self, "PDF Seç", "", "PDF (*.pdf)")
        if path:
            if self.load_pdf_file(path):
                self.current_page = 1
                self.load_current_page()

    def load_pdf_file(self, path):
        """Verilen path'teki PDF'i açar (Mantıksal yükleme)."""
        try:
            self.doc = pymupdf.open(path)
            self.total_pages = len(self.doc)
            self.log(f"PDF Yüklendi: {os.path.basename(path)} ({self.total_pages} sayfa)")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF açılamadı:\n{str(e)}")
            return False

    def load_current_page(self):
        """Mevcut self.current_page'i ekrana ve viewer'a yükler."""
        if not self.doc: return
        
        try:
            # 1. Viewer'a resmi yükle (Arkaplanı temizler)
            # PyMuPDF sayfa indexi 0'dan başlar, biz 1'den sayıyoruz.
            page_index = self.current_page - 1
            page = self.doc.load_page(page_index)
            self.viewer.set_background_image(page)
            
            # 2. UI Durumlarını Güncelle
            self.status_bar.showMessage(f"Sayfa {self.current_page} yüklendi.")
            self.lbl_page.setText(f" Sayfa: {self.current_page} / {self.total_pages} ")
            
            # Navigasyon butonlarını kontrol et
            self.act_prev.setEnabled(self.current_page > 1)
            self.act_next.setEnabled(self.current_page < self.total_pages)
            
            # Analiz butonunu aktif et
            self.act_analyze.setEnabled(True)
            
            # Eski analiz sonuçlarını ve bağlantı butonunu sıfırla
            self.act_check.setEnabled(False)
            if hasattr(self, 'current_result'): 
                del self.current_result
            
            # Kutu çizme modundaysa NAVIGATE'e geri alabiliriz (isteğe bağlı)
            # self.set_mode("NAVIGATE") 

        except Exception as e:
            self.log(f"Sayfa yükleme hatası: {e}")

    def prev_page(self):
        """Önceki sayfaya geçer."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_current_page()

    def next_page(self):
        """Sonraki sayfaya geçer."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_current_page()

    def set_mode(self, mode):
        """Modlar arası geçiş yapar."""
        if mode == "NAVIGATE":
            self.act_nav.setChecked(True); self.act_draw.setChecked(False)
            self.viewer.set_mode("NAVIGATE")
            self.status_bar.showMessage("Mod: Gezinme")
        else:
            self.act_nav.setChecked(False); self.act_draw.setChecked(True)
            self.viewer.set_mode("DRAW")
            self.status_bar.showMessage("Mod: Kutu Çizme (Hattın ucuna kutu çizin)")

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
        
        # Ekrana Çiz
        self.viewer.draw_analysis_result(result)
        self.act_check.setEnabled(True)
        self.act_ocr_test.setEnabled(True)
        
        self.log(f"Analiz Bitti. {len(result.structural_groups)} hat bulundu.")
        
        # Otomatik olarak bağlantı kontrolünü başlat
        self.run_connection_check()

    def run_connection_check(self):
        # 1. Çizilen kutuları al
        manual_boxes = self.viewer.get_drawn_components()
        
        if not hasattr(self, 'current_result'):
            self.log("UYARI: Önce 'Analiz Et' butonuna basmalısınız.")
            return

        # 2. Otomatik bulunan klemensleri CircuitComponent'e çevir
        terminal_components = []
        if hasattr(self.current_result, 'terminals') and self.current_result.terminals:
            from .circuit_logic import CircuitComponent
            for term in self.current_result.terminals:
                # Klemens için Bounding Box oluştur (Merkez +/- Yarıçap)
                cx, cy = term['center']
                r = term['radius']
                margin = 2.0
                
                term_id = term.get('full_label') or f"TERM-{len(terminal_components)+1}"
                
                comp = CircuitComponent(
                    id=term_id,
                    label="Terminal",
                    bbox={
                        "min_x": cx - r - margin,
                        "min_y": cy - r - margin,
                        "max_x": cx + r + margin,
                        "max_y": cy + r + margin
                    }
                )
                terminal_components.append(comp)

        # 3. Tüm bileşenleri birleştir
        all_components = manual_boxes + terminal_components
        
        # 4. Bağlantıları hesapla
        from .circuit_logic import check_intersections
        connections = check_intersections(all_components, self.current_result)
        
        self.log("\n====== BAĞLANTI RAPORU ======")
        found_any = False
        
        # 5. Sonuçları Hiyerarşik Yazdır
        sorted_nets = sorted(connections.keys())
        
        for net_id in sorted_nets:
            comp_ids = connections[net_id]
            
            if comp_ids:
                self.log(f"🔹 {net_id} Hattı:")
                for comp_id in comp_ids:
                    self.log(f"   └─ 🔌 {comp_id}")
                found_any = True
        
        if not found_any:
            self.log("❌ Hiçbir bağlantı bulunamadı.")
            self.log("İpucu: Klemensler veya kutular hatların üzerine gelmiyor olabilir.")

    def on_error(self, msg):
        self.act_analyze.setEnabled(True)
        self.status_bar.showMessage("Hata!")
        QMessageBox.critical(self, "Analiz Hatası", msg)

    def log(self, msg):
        self.log_text.append(msg)

    def run_ocr_test(self):
        """OCR ve PDF karşılaştırma işlemini başlatır."""
        if not hasattr(self, 'current_result'):
            return

        self.log("\n====== OCR vs PDF KARŞILAŞTIRMA ======")
        self.log("NOT: Bu işlem biraz zaman alabilir (GPU/CPU gücüne bağlı)...")
        self.act_ocr_test.setEnabled(False) # Tekrar basılmasın
        
        # Worker Başlat
        self.ocr_worker = OCRComparisonWorker(self.doc, self.current_page, self.current_result)
        self.ocr_worker.log_signal.connect(self.log) # Logları ekrana bas
        self.ocr_worker.finished_signal.connect(self.on_ocr_finished)
        self.ocr_worker.start()

    def on_ocr_finished(self):
        self.act_ocr_test.setEnabled(True)
        self.status_bar.showMessage("OCR Testi Bitti.")
        self.log("====== TEST BİTTİ ======")