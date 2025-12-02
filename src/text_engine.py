import math
import re
import numpy as np
import pymupdf
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Union

# EasyOCR opsiyoneldir
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

class SearchDirection(Enum):
    ANY = "any"
    TOP = "top"
    BOTTOM = "bottom"
    RIGHT = "right"
    LEFT = "left"
    TOP_RIGHT = "top_right"
    TOP_LEFT = "top_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"

@dataclass
class TextElement:
    text: str
    center: Tuple[float, float]
    bbox: Tuple[float, float, float, float]
    source: str
    confidence: float = 1.0

@dataclass
class SearchProfile:
    search_radius: float = 30.0
    direction: SearchDirection = SearchDirection.ANY
    regex_pattern: Optional[str] = None
    use_ocr_fallback: bool = True
    ocr_lang_list: list = None

class HybridTextEngine:
    def __init__(self, languages=['en']):
        self.languages = languages
        self.ocr_reader = None
        self.current_page = None
        self.pdf_elements: List[TextElement] = []

    def load_page(self, page: pymupdf.Page):
        """Sayfa yüklendiğinde metin katmanını hafızaya alır."""
        self.current_page = page
        self.pdf_elements = []
        
        # Hızlı okuma (Dictionary formatı)
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
        """Otomatik olarak önce PDF, sonra OCR bakar."""
        ox = origin_point.x if hasattr(origin_point, 'x') else origin_point[0]
        oy = origin_point.y if hasattr(origin_point, 'y') else origin_point[1]

        # 1. PDF Katmanı
        best_match = self._search_in_list(self.pdf_elements, ox, oy, profile)
        if best_match:
            return best_match
            
        # 2. OCR Katmanı (Fallback)
        if profile.use_ocr_fallback and EASYOCR_AVAILABLE and self.current_page:
            return self._perform_region_ocr(ox, oy, profile)
            
        return None

    def find_text_only_pdf(self, origin_point, profile: SearchProfile) -> Optional[TextElement]:
        """Sadece PDF katmanında arama yapar (Karşılaştırma raporları için)."""
        ox = origin_point.x if hasattr(origin_point, 'x') else origin_point[0]
        oy = origin_point.y if hasattr(origin_point, 'y') else origin_point[1]
        return self._search_in_list(self.pdf_elements, ox, oy, profile)

    def find_text_only_ocr(self, origin_point, profile: SearchProfile) -> Optional[TextElement]:
        """Sadece OCR yapar (Karşılaştırma raporları için)."""
        if not EASYOCR_AVAILABLE or not self.current_page:
            return None
        ox = origin_point.x if hasattr(origin_point, 'x') else origin_point[0]
        oy = origin_point.y if hasattr(origin_point, 'y') else origin_point[1]
        return self._perform_region_ocr(ox, oy, profile)

    def _search_in_list(self, elements: List[TextElement], ox, oy, profile) -> Optional[TextElement]:
        candidates = []
        for elem in elements:
            dist = math.sqrt((elem.center[0] - ox)**2 + (elem.center[1] - oy)**2)
            if dist > profile.search_radius:
                continue
            
            if profile.regex_pattern and not re.match(profile.regex_pattern, elem.text):
                continue
            
            if not self._check_direction(ox, oy, elem.center[0], elem.center[1], profile.direction):
                continue
                
            candidates.append((dist, elem))
            
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        return None

    def _perform_region_ocr(self, ox, oy, profile) -> Optional[TextElement]:
        if not self.ocr_reader:
            # Lazy Loading
            self.ocr_reader = easyocr.Reader(
                profile.ocr_lang_list if profile.ocr_lang_list else self.languages, 
                gpu=True, verbose=False
            )

        r = profile.search_radius + 15
        rect = pymupdf.Rect(ox - r, oy - r, ox + r, oy + r)
        
        # 3x Zoom ile görüntü kalitesini artır
        mat = pymupdf.Matrix(3, 3)
        pix = self.current_page.get_pixmap(matrix=mat, clip=rect)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        allowlist = "0123456789" if profile.regex_pattern == r"^\d+$" else None
        results = self.ocr_reader.readtext(img_np, allowlist=allowlist, rotation_info=[90, 270])

        ocr_elements = []
        for bbox, text, conf in results:
            if conf < 0.4: continue
            
            local_cx = (bbox[0][0] + bbox[2][0]) / 2
            local_cy = (bbox[0][1] + bbox[2][1]) / 2
            
            # Koordinatları global sisteme geri çevir
            global_cx = (local_cx / 3) + (ox - r)
            global_cy = (local_cy / 3) + (oy - r)
            
            ocr_elements.append(TextElement(
                text=text, center=(global_cx, global_cy),
                bbox=(0,0,0,0), source='ocr', confidence=conf
            ))
            
        return self._search_in_list(ocr_elements, ox, oy, profile)
        
    def _check_direction(self, ox, oy, tx, ty, direction: SearchDirection) -> bool:
        if direction == SearchDirection.ANY: return True
        
        dx = tx - ox
        dy = ty - oy
        angle = math.degrees(math.atan2(dy, dx))
        
        # Açı kontrolleri (Y aşağı artıyor)
        if direction == SearchDirection.RIGHT: return -45 <= angle <= 45
        elif direction == SearchDirection.BOTTOM: return 45 <= angle <= 135
        elif direction == SearchDirection.LEFT: return 135 <= angle <= 180 or -180 <= angle <= -135
        elif direction == SearchDirection.TOP: return -135 <= angle <= -45
        elif direction == SearchDirection.TOP_RIGHT: return -90 <= angle <= 0
        elif direction == SearchDirection.TOP_LEFT: return -180 <= angle <= -90
        
        return False