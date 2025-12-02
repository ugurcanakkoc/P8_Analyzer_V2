from PyQt5.QtCore import QThread, pyqtSignal
import pymupdf
import traceback

# NOT: Bu importu projenin dosya yapısına göre kontrol edin.
# Eğer 'src' klasörü ana dizindeyse: 'from src.models import ...'
try:
    from external.uvp.src import analyze_page_vectors, DEFAULT_CONFIG
except ImportError:
    # Fallback: Eğer external klasörü yoksa, src direkt erişilebilir varsay
    from src.analysis_core import analyze_page_vectors, DEFAULT_CONFIG

class AnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, pdf_path, page_num):
        """
        Thread Safety için 'doc' nesnesi yerine dosya yolu (pdf_path) alır.
        """
        super().__init__()
        self.pdf_path = pdf_path
        self.page_num = page_num

    def run(self):
        doc = None
        try:
            # Thread içinde dosyayı güvenli şekilde aç
            doc = pymupdf.open(self.pdf_path)
            page_index = self.page_num - 1
            page = doc.load_page(page_index)
            
            drawings = page.get_drawings()
            if not drawings:
                self.error.emit("Bu sayfada vektör verisi bulunamadı.")
                return

            # Vektör Analizi
            analysis_result = analyze_page_vectors(drawings, page.rect, self.page_num, DEFAULT_CONFIG)
            
            # --- TERMINAL ANALİZİ ---
            try:
                from src.terminal_detector import TerminalDetector
                from src.terminal_reader import TerminalReader
                from src.terminal_grouper import TerminalGrouper
                from src.text_engine import HybridTextEngine
                
                # 1. Tespit
                detector = TerminalDetector()
                terminals = detector.detect(analysis_result)
                
                if terminals:
                    # 2. Okuma (TextEngine bu thread'deki page nesnesini kullanmalı)
                    text_engine = HybridTextEngine(languages=['en'])
                    text_engine.load_page(page)
                    
                    reader = TerminalReader()
                    terminals = reader.read_labels(terminals, text_engine)
                    
                    # 3. Gruplama
                    grouper = TerminalGrouper()
                    terminals = grouper.group_terminals(terminals, text_engine)
                    
                    # 4. Sonucu modele ekle
                    analysis_result.terminals = terminals
                    
            except ImportError:
                print("Terminal modülleri bulunamadı, bu adım atlanıyor.")
            except Exception as e:
                print(f"Terminal analizi hatası: {e}")
                traceback.print_exc()
            
            # Sonucu gönder
            self.finished.emit(analysis_result)

        except Exception as e:
            self.error.emit(f"Kritik Hata:\n{str(e)}\n{traceback.format_exc()}")
        finally:
            if doc:
                doc.close()