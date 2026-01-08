# Dosya: src/device_tagger.py

import re
from typing import Optional, Tuple
from p8_analyzer.text import HybridTextEngine, SearchProfile, SearchDirection

class DeviceTagger:
    """
    Cihaz kutularının (Box) etiketlerini (BMK) bulur.
    Genelde kutunun sol üst köşesinde veya hemen üzerinde yer alır.
    Örn: -K1, -3Q12, -X4
    """
    def __init__(self, text_engine: HybridTextEngine):
        self.text_engine = text_engine
        
        # Regex Açıklaması:
        # ^-       -> Tire ile başlamalı
        # [A-Z0-9] -> Harf veya rakamla devam etmeli
        # .        -> Araya nokta girebilir (örn: -X4.1)
        # {1,10}   -> 1 ila 10 karakter uzunluğunda
        self.bmk_pattern = r"^-[A-Z0-9\.]+$"

    def find_tag(self, bbox: Tuple[float, float, float, float]) -> Optional[str]:
        """
        Verilen BoundingBox (min_x, min_y, max_x, max_y) için etiket arar.
        """
        min_x, min_y, max_x, max_y = bbox
        
        # Strateji: Kutunun sol üst köşesine (Top-Left) odaklan.
        # Hem kutunun biraz içine, hem de biraz dışına (yukarısına) bakmalıyız.
        
        # Arama Merkezi: Sol üst köşe
        search_center_x = min_x
        search_center_y = min_y
        
        # Arama Yarıçapı: 50 birim (Bu değer çizim ölçeğine göre ayarlanabilir)
        search_radius = 60.0 
        
        # Profil Oluştur
        profile = SearchProfile(
            search_radius=search_radius,
            direction=SearchDirection.ANY, # Sol üst etrafındaki her şeye bak
            regex_pattern=self.bmk_pattern,
            use_ocr_fallback=True # PDF'de metin yoksa OCR yap
        )
        
        # Text Engine ile ara
        # Not: Arama noktasını biraz içeri kaydırabiliriz ama köşe en garantisidir.
        result = self.text_engine.find_text((search_center_x, search_center_y), profile)
        
        if result:
            return result.text
            
        return None