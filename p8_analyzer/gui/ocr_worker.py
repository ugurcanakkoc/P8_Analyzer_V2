from PyQt5.QtCore import QThread, pyqtSignal
import pymupdf
import traceback
from p8_analyzer.text import HybridTextEngine, SearchProfile, SearchDirection
from p8_analyzer.core import Point

class OCRComparisonWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, pdf_path, page_num, analysis_result):
        super().__init__()
        self.pdf_path = pdf_path
        self.page_num = page_num
        self.analysis_result = analysis_result
        self.is_running = True

    def run(self):
        doc = None
        try:
            self.log_signal.emit("OCR Motoru ve Belge Hazırlanıyor...")
            doc = pymupdf.open(self.pdf_path)
            page = doc.load_page(self.page_num - 1)
            
            engine = HybridTextEngine(languages=['en'])
            engine.load_page(page)
            
            profile = SearchProfile(
                search_radius=30.0,
                direction=SearchDirection.ANY,
                use_ocr_fallback=True
            )
            
            count = len(self.analysis_result.structural_groups)
            self.log_signal.emit(f"Toplam {count} hat taranacak...")
            
            for i, group in enumerate(self.analysis_result.structural_groups):
                if not self.is_running: break
                
                net_id = f"NET-{i+1:03d}"
                # Basitlik için sadece başlangıç noktalarına bakalım
                points_to_scan = [group.elements[0].start_point] if group.elements else []
                
                for pt in points_to_scan:
                    # PDF vs OCR Karşılaştırması
                    pdf_res = engine.find_text_only_pdf(pt, profile)
                    ocr_res = engine.find_text_only_ocr(pt, profile)
                    
                    pdf_txt = pdf_res.text if pdf_res else "---"
                    ocr_txt = ocr_res.text if ocr_res else "---"
                    
                    if pdf_txt != "---" or ocr_txt != "---":
                        match_state = "✅" if pdf_txt == ocr_txt else "⚠️ Farklı"
                        if pdf_txt == "---": match_state = "📷 Sadece OCR"
                        if ocr_txt == "---": match_state = "📄 Sadece PDF"
                        
                        self.log_signal.emit(f"{net_id}: PDF[{pdf_txt}] - OCR[{ocr_txt}] {match_state}")
            
            self.log_signal.emit("İşlem Tamamlandı.")
            
        except Exception as e:
            self.log_signal.emit(f"Hata: {str(e)}")
            traceback.print_exc()
        finally:
            if doc: doc.close()
            self.finished_signal.emit()

    def stop(self):
        self.is_running = False