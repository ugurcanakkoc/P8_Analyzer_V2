# gui/worker.py
from PyQt5.QtCore import QThread, pyqtSignal
from external.uvp.src import analyze_page_vectors, DEFAULT_CONFIG

class AnalysisWorker(QThread):
    """
    PDF analizini arka planda yapar ve sonucu ham veri (nesne) olarak döndürür.
    Artık PNG oluşturmuyoruz, veriyi canlı çizeceğiz.
    """
    finished = pyqtSignal(object)  # VectorAnalysisResult nesnesi döndürür
    error = pyqtSignal(str)

    def __init__(self, doc, page_num):
        super().__init__()
        self.doc = doc
        self.page_num = page_num

    def run(self):
        try:
            page_index = self.page_num - 1
            page = self.doc.load_page(page_index)
            drawings = page.get_drawings()
            page_rect = page.rect
            
            if not drawings:
                self.error.emit("Bu sayfada vektör verisi bulunamadı.")
                return

            # Analizi başlat (PNG export yok, sadece veri)
            analysis_result = analyze_page_vectors(drawings, page_rect, self.page_num, DEFAULT_CONFIG)
            
            # --- TERMINAL ANALİZİ (Klemens Bulma) ---
            try:
                from src.terminal_detector import TerminalDetector
                from src.terminal_reader import TerminalReader
                from src.terminal_grouper import TerminalGrouper
                from src.text_engine import HybridTextEngine
                
                # 1. Klemensleri Tespit Et (Dairelerden)
                detector = TerminalDetector()
                terminals = detector.detect(analysis_result)
                
                if terminals:
                    # 2. Metin Motorunu Hazırla
                    text_engine = HybridTextEngine(languages=['en'])
                    text_engine.load_page(page)
                    
                    # 3. Etiketleri Oku (1, 2, PE, N vb.)
                    reader = TerminalReader()
                    terminals = reader.read_labels(terminals, text_engine)
                    
                    # 4. Grupları Belirle (-X1, -X2 vb.)
                    grouper = TerminalGrouper()
                    terminals = grouper.group_terminals(terminals, text_engine)
                    
                    # 5. Sonucu Kaydet
                    analysis_result.terminals = terminals
                    print(f"Terminal Analizi Tamamlandı: {len(terminals)} klemens bulundu.")
                    
            except Exception as e:
                print(f"Terminal analizi sırasında hata: {e}")
                import traceback
                traceback.print_exc()
                # Ana analiz bozulmasın, devam et
            
            self.finished.emit(analysis_result)

        except Exception as e:
            import traceback
            self.error.emit(f"Analiz Hatası:\n{str(e)}\n{traceback.format_exc()}")