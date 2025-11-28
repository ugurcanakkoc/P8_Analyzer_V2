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
            
            self.finished.emit(analysis_result)

        except Exception as e:
            import traceback
            self.error.emit(f"Analiz Hatası:\n{str(e)}\n{traceback.format_exc()}")