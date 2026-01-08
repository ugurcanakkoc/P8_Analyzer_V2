import logging
from typing import List, Dict, Optional, Any
from p8_analyzer.text import HybridTextEngine, SearchProfile, SearchDirection

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
                text_element = self._find_label_element_near_point(point, text_engine)
                
                if text_element and self._is_valid_pin_label(text_element.text):
                    label = text_element.text
                    text_center = text_element.center
                    
                    # Duplicate Check Logic based on TEXT LOCATION
                    is_same_text_object = False
                    duplicate_count = 0
                    
                    for existing_pin in pins:
                        if existing_pin['pin_label'] == label and existing_pin['box_id'] == found_box.id:
                            duplicate_count += 1
                            
                            # Check distance between TEXT CENTERS
                            # If the text centers are very close, it's the same text object (ghost detection)
                            ex, ey = existing_pin['text_center']
                            import math
                            text_dist = math.sqrt((ex - text_center[0])**2 + (ey - text_center[1])**2)
                            
                            if text_dist < 2.0: # Same text object found again
                                is_same_text_object = True
                                break
                    
                    if not is_same_text_object:
                        final_label = label
                        if duplicate_count > 0:
                            final_label = f"{label} ({duplicate_count + 1})"
                            
                        full_label = f"{found_box.id}:{final_label}"
                        
                        pins.append({
                            'box_id': found_box.id,
                            'pin_label': label,
                            'full_label': full_label,
                            'location': (point.x, point.y),
                            'text_center': text_center # Store text location for deduplication
                        })
                        self._log_debug(f"✅ PIN BULUNDU: {full_label} (Raw: {label})")
                    else:
                        self._log_debug(f"⚠️ DUPLICATE TEXT SKIPPED: {label}")
        return pins

    def _find_label_element_near_point(self, point, text_engine) -> Optional[Any]:
        """TextEngine kullanarak nokta çevresinde etiket arar ve TextElement döner."""
        profile = SearchProfile(
            search_radius=self.search_radius,
            direction=SearchDirection.ANY, 
            regex_pattern=r'^[a-zA-Z0-9\.\-\/\+]+$', # Alphanumeric, +, -, ., /
            use_ocr_fallback=True
        )
        
        # TextEngine'e işi devrediyoruz
        return text_engine.find_text(point, profile)

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