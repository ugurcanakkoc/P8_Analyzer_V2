import math
import re
import numpy as np
import pymupdf
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Union
from PIL import Image

# EasyOCR opsiyoneldir. Yüklü değilse program çökmez, sadece OCR yapmaz.
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("UYARI: 'easyocr' kütüphanesi bulunamadı. OCR özellikleri devre dışı kalacak.")

# --- ENUM & DATA MODELS ---

class SearchDirection(Enum):
    ANY = "any"             # Yön fark etmez
    TOP = "top"             # Üst
    BOTTOM = "bottom"       # Alt
    RIGHT = "right"         # Sağ
    LEFT = "left"           # Sol
    TOP_RIGHT = "top_right" # Sağ Üst
    TOP_LEFT = "top_left"   # Sol Üst
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"

@dataclass
class TextElement:
    text: str
    center: Tuple[float, float]     # (x, y)
    bbox: Tuple[float, float, float, float] # (x0, y0, x1, y1)
    source: str                     # 'pdf' veya 'ocr'
    confidence: float = 1.0

@dataclass
class SearchProfile:
    """Arama konfigürasyonu"""
    search_radius: float = 30.0     # Arama yarıçapı
    direction: SearchDirection = SearchDirection.ANY
    regex_pattern: Optional[str] = None  # Örn: r"^-?[A-Z][0-9]+$"
    use_ocr_fallback: bool = True        # PDF'de yoksa OCR yap?
    ocr_lang_list: list = None           # Varsayılan ['en']

# --- MAIN ENGINE ---

class HybridTextEngine:
    def __init__(self, languages=['en']):
        self.languages = languages
        self.ocr_reader = None
        self.current_page = None
        self.pdf_elements: List[TextElement] = []

    def load_page(self, page: pymupdf.Page):
        """
        Sayfa yüklendiğinde metin katmanını hafızaya alır.
        Bu işlem çok hızlıdır.
        """
        self.current_page = page
        self.pdf_elements = []
        
        # PyMuPDF ile metinleri çek (Fast Layer)
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text: continue
                        
                        bbox = span["bbox"]
                        cx = (bbox[0] + bbox[2]) / 2
                        cy = (bbox[1] + bbox[3]) / 2
                        
                        self.pdf_elements.append(TextElement(
                            text=text,
                            center=(cx, cy),
                            bbox=bbox,
                            source='pdf',
                            confidence=1.0
                        ))

    def find_text(self, origin_point, profile: SearchProfile) -> Optional[TextElement]:
        """
        Verilen nokta (origin_point) etrafında kriterlere uyan metni arar.
        """
        # Point objesi veya tuple gelebilir
        ox = origin_point.x if hasattr(origin_point, 'x') else origin_point[0]
        oy = origin_point.y if hasattr(origin_point, 'y') else origin_point[1]

        # 1. KATMAN: PDF Metinlerinde Ara
        best_match = self._search_in_list(self.pdf_elements, ox, oy, profile)
        if best_match:
            return best_match
            
        # 2. KATMAN: OCR Fallback
        # Eğer PDF'de bulamadıysak, EasyOCR var mı ve izin verilmiş mi?
        if profile.use_ocr_fallback and EASYOCR_AVAILABLE and self.current_page:
            return self._perform_region_ocr(ox, oy, profile)
            
        return None

    def _search_in_list(self, elements: List[TextElement], ox, oy, profile) -> Optional[TextElement]:
        """Verilen listede filtreleme yapar (Mesafe, Yön, Regex)."""
        candidates = []
        
        for elem in elements:
            # A. Mesafe Filtresi
            dist = math.sqrt((elem.center[0] - ox)**2 + (elem.center[1] - oy)**2)
            if dist > profile.search_radius:
                continue
            
            # B. Regex Filtresi
            if profile.regex_pattern:
                # Regex eşleşmiyorsa atla
                if not re.match(profile.regex_pattern, elem.text):
                    continue
            
            # C. Yön Filtresi
            if not self._check_direction(ox, oy, elem.center[0], elem.center[1], profile.direction):
                continue
                
            candidates.append((dist, elem))
            
        if candidates:
            # En yakını seç
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
            
        return None

    def _perform_region_ocr(self, ox, oy, profile) -> Optional[TextElement]:
        """Bölgesel OCR işlemi yapar (Sadece ilgili kareyi kesip okur)."""
        if not self.ocr_reader:
            # Reader'ı ilk ihtiyaç duyulduğunda yükle (Lazy Loading)
            print("OCR Motoru Başlatılıyor (Bu işlem bir kez yapılır)...")
            self.ocr_reader = easyocr.Reader(
                profile.ocr_lang_list if profile.ocr_lang_list else self.languages, 
                gpu=True
            )

        # 1. İlgili bölgeyi kırp (Crop)
        r = profile.search_radius + 15 # Biraz pay bırak
        rect = pymupdf.Rect(ox - r, oy - r, ox + r, oy + r)
        
        # Görüntü kalitesini artır (3x Zoom) -> OCR başarısını artırır
        mat = pymupdf.Matrix(3, 3)
        pix = self.current_page.get_pixmap(matrix=mat, clip=rect)
        
        # PIL formatına çevir
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        # 2. OCR Yap
        # allowlist optimizasyonu: Sadece rakam aranıyorsa diğerlerini tarama
        allowlist = None
        if profile.regex_pattern == r"^\d+$":
            allowlist = "0123456789"
            
        # rotation_info: 90 ve 270 derece dönmüş yazıları da oku
        results = self.ocr_reader.readtext(img_np, allowlist=allowlist, rotation_info=[90, 270])

        ocr_elements = []
        for bbox, text, conf in results:
            if conf < 0.4: continue # Düşük güvenli sonuçları at
            
            # Koordinat dönüşümü (Local -> Global)
            # bbox = [[x1, y1], [x2, y1], ... ]
            local_cx = (bbox[0][0] + bbox[2][0]) / 2
            local_cy = (bbox[0][1] + bbox[2][1]) / 2
            
            # Zoom etkisini (3x) geri al ve offset ekle
            global_cx = (local_cx / 3) + (ox - r)
            global_cy = (local_cy / 3) + (oy - r)
            
            ocr_elements.append(TextElement(
                text=text,
                center=(global_cx, global_cy),
                bbox=(0,0,0,0), # Detaylı bbox gerekirse hesaplanabilir
                source='ocr',
                confidence=conf
            ))
            
        # 3. Bulunan OCR sonuçları içinde arama yap
        return self._search_in_list(ocr_elements, ox, oy, profile)

    # src/text_engine.py dosyasındaki HybridTextEngine sınıfına ekleyin:

    def find_text_only_pdf(self, origin_point, profile: SearchProfile) -> Optional[TextElement]:
        """Sadece PDF katmanında arama yapar."""
        ox = origin_point.x if hasattr(origin_point, 'x') else origin_point[0]
        oy = origin_point.y if hasattr(origin_point, 'y') else origin_point[1]
        return self._search_in_list(self.pdf_elements, ox, oy, profile)

    def find_text_only_ocr(self, origin_point, profile: SearchProfile) -> Optional[TextElement]:
        """Sadece Bölgesel OCR yapar (PDF katmanını yok sayar)."""
        if not EASYOCR_AVAILABLE or not self.current_page:
            return None
            
        ox = origin_point.x if hasattr(origin_point, 'x') else origin_point[0]
        oy = origin_point.y if hasattr(origin_point, 'y') else origin_point[1]
        
        # Direkt OCR fonksiyonunu çağır
        return self._perform_region_ocr(ox, oy, profile)
        
    def _check_direction(self, ox, oy, tx, ty, direction: SearchDirection) -> bool:
        """Hedef noktanın (tx, ty), kaynağa (ox, oy) göre yönünü kontrol eder."""
        if direction == SearchDirection.ANY: 
            return True
            
        # Açı hesapla (Radyan -> Derece)
        # PDF'de Y aşağı doğru arttığı için koordinat sistemine dikkat edilmeli
        dx = tx - ox
        dy = ty - oy
        angle = math.degrees(math.atan2(dy, dx))
        
        # Atan2 Sonuçları (Y aşağı artarken):
        # 0: Sağ, 90: Aşağı, 180/-180: Sol, -90: Yukarı
        
        if direction == SearchDirection.RIGHT:       # -45 ile 45 arası
            return -45 <= angle <= 45
        elif direction == SearchDirection.BOTTOM:    # 45 ile 135 arası
            return 45 <= angle <= 135
        elif direction == SearchDirection.LEFT:      # 135 ile 180 VEYA -180 ile -135
            return 135 <= angle <= 180 or -180 <= angle <= -135
        elif direction == SearchDirection.TOP:       # -135 ile -45 arası
            return -135 <= angle <= -45
            
        # Ara yönler (45 derecelik dilimler)
        elif direction == SearchDirection.TOP_RIGHT: # -90 ile 0 arası (kabaca)
            return -90 <= angle <= 0
        elif direction == SearchDirection.TOP_LEFT:  # -180 ile -90 arası
            return -180 <= angle <= -90
            
        return False