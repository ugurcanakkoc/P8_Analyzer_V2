import logging
from typing import List, Dict, Optional, Any
from src.text_engine import HybridTextEngine, SearchProfile, SearchDirection

logger = logging.getLogger(__name__)

class PinFinder:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.search_radius = self.config.get('pin_search_radius', 75.0)
        self.debug_callback = None

    def set_debug_callback(self, callback):
        self.debug_callback = callback

    def _log_debug(self, msg):
        if self.debug_callback:
            self.debug_callback(msg)
        else:
            logger.debug(msg)
        
    def find_pins_for_group(self, group, boxes: List[Any], text_engine: HybridTextEngine) -> List[Dict]:
        pins = []
        # Grubun tüm noktalarını (çizgi uçları) al
        all_points = self._get_all_group_points(group)
        
        for point in all_points:
            # Sadece bir kutunun içindeki noktalara bak (Gürültü önleme)
            found_box = None
            for box in boxes:
                if box.contains_point(point):
                    found_box = box
                    break
            
            if found_box:
                # TextEngine ile akıllı arama yap (PDF + OCR)
                label = self._find_label_near_point(point, text_engine)
                
                if label and self._is_valid_pin_label(label):
                    # Duplicate (aynı pin) kontrolü
                    is_duplicate = False
                    for existing in pins:
                        if existing['pin_label'] == label and existing['box_id'] == found_box.id:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        full_label = f"{found_box.id}:{label}"
                        pins.append({
                            'box_id': found_box.id,
                            'pin_label': label,
                            'full_label': full_label,
                            'location': (point.x, point.y)
                        })
                        self._log_debug(f"✅ PIN BULUNDU: {full_label}")
        return pins

    def _find_label_near_point(self, point, text_engine) -> Optional[str]:
        """TextEngine kullanarak nokta çevresinde etiket arar."""
        profile = SearchProfile(
            search_radius=self.search_radius,
            direction=SearchDirection.ANY, 
            regex_pattern=r'^[a-zA-Z0-9\.\-\/\+]+$', # Alphanumeric, +, -, ., /
            use_ocr_fallback=True
        )
        
        # TextEngine'e işi devrediyoruz
        result = text_engine.find_text(point, profile)
        return result.text if result else None

    def _is_valid_pin_label(self, label: str) -> bool:
        if not label: return False
        if len(label) > 12: return False 
        if len(label) < 1: return False
        return True

    def _get_all_group_points(self, group) -> List[Any]:
        """Hattın tüm uç noktalarını döndürür."""
        class SimplePoint:
            def __init__(self, x, y): self.x, self.y = x, y
            
        unique_points = set()
        result_points = []
        
        for elem in group.elements:
            # Koordinatları yuvarla ki mikronluk farklar yüzünden duplicate olmasın
            p1 = (round(elem.start_point.x, 2), round(elem.start_point.y, 2))
            p2 = (round(elem.end_point.x, 2), round(elem.end_point.y, 2))
            
            if p1 not in unique_points:
                unique_points.add(p1)
                result_points.append(SimplePoint(p1[0], p1[1]))
            if p2 not in unique_points:
                unique_points.add(p2)
                result_points.append(SimplePoint(p2[0], p2[1]))
                
        return result_points