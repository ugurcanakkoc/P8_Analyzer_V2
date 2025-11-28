# gui/ocr_worker.py

from PyQt5.QtCore import QThread, pyqtSignal
from src.text_engine import HybridTextEngine, SearchProfile, SearchDirection
from src.models import Point

class OCRComparisonWorker(QThread):
    """
    Tüm bağlantı uçlarını gezer, hem PDF hem OCR taraması yapar ve sonucu raporlar.
    """
    log_signal = pyqtSignal(str)     # Anlık log atmak için
    finished_signal = pyqtSignal()   # İşlem bitince

    def __init__(self, doc, page_num, analysis_result):
        super().__init__()
        self.doc = doc
        self.page_num = page_num
        self.analysis_result = analysis_result
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit("OCR Motoru Başlatılıyor...")
            
            # Motoru hazırla
            engine = HybridTextEngine(languages=['en']) # Gerekirse ['en', 'tr']
            page = self.doc.load_page(self.page_num - 1)
            engine.load_page(page)
            
            # Arama Profili (Genel Amaçlı)
            profile = SearchProfile(
                search_radius=30.0,            # 30 birim çevreye bak
                direction=SearchDirection.ANY, # Her yöne bak
                regex_pattern=None,            # Her şeyi kabul et (Regex ile filtreleme yapma şimdilik)
                use_ocr_fallback=True
            )
            
            self.log_signal.emit(f"Toplam {len(self.analysis_result.structural_groups)} hat taranacak...")
            
            # Her bir hat grubu için
            for i, group in enumerate(self.analysis_result.structural_groups):
                if not self.is_running: break
                
                net_id = f"NET-{i+1:03d}"
                
                # Uç noktaları belirle (Başlangıç ve Bitiş noktaları)
                # Basitlik için grubun tüm elemanlarının uçlarına bakıyoruz
                # (Daha gelişmiş versiyonda sadece "açıkta kalan" uçlara bakılabilir)
                points_to_scan = set()
                for elem in group.elements:
                    points_to_scan.add((elem.start_point.x, elem.start_point.y))
                    points_to_scan.add((elem.end_point.x, elem.end_point.y))
                
                for pt_tuple in points_to_scan:
                    pt = Point(x=pt_tuple[0], y=pt_tuple[1])
                    
                    # 1. PDF Taraması
                    pdf_res = engine.find_text_only_pdf(pt, profile)
                    pdf_txt = pdf_res.text if pdf_res else "---"
                    
                    # 2. OCR Taraması
                    ocr_res = engine.find_text_only_ocr(pt, profile)
                    ocr_txt = ocr_res.text if ocr_res else "---"
                    
                    # Eğer ikisinden biri bir şey bulduysa raporla
                    if pdf_res or ocr_res:
                        # Koordinatı string yap
                        coord_str = f"({int(pt.x)},{int(pt.y)})"
                        
                        # Eşleşme durumu
                        match_icon = "✅" if pdf_txt == ocr_txt and pdf_txt != "---" else "⚠️"
                        if pdf_txt == "---" and ocr_txt != "---": match_icon = "📷(OCR)"
                        if pdf_txt != "---" and ocr_txt == "---": match_icon = "📄(PDF)"
                        
                        log_msg = (f"{net_id} {coord_str} -> "
                                   f"PDF: [{pdf_txt}] | OCR: [{ocr_txt}] {match_icon}")
                        self.log_signal.emit(log_msg)
            
            self.log_signal.emit("\nKarşılaştırma Tamamlandı.")
            
        except Exception as e:
            import traceback
            self.log_signal.emit(f"Hata: {str(e)}\n{traceback.format_exc()}")
        finally:
            self.finished_signal.emit()

    def stop(self):
        self.is_running = False