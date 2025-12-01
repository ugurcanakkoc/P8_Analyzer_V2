import logging
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict

from src.text_engine import HybridTextEngine, SearchProfile, SearchDirection
# Assuming Point and StructuralGroup are available here or we handle them generically
# from external.uvp.src.models import StructuralGroup, Point 

logger = logging.getLogger(__name__)

class PinFinder:
    """
    Module for detecting pin labels at the open ends of connection lines,
    specifically those located inside defined component boxes.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        # Search radius for pin labels (increased to catch labels slightly further away)
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
        """
        Finds pins for a specific net (group) that fall inside the given boxes.
        Strictly searches ONLY inside boxes to avoid noise.
        """
        pins = []
        
        # 1. Get ALL points in the group (start and end of every line segment)
        all_points = self._get_all_group_points(group)
        
        points_inside_box = 0
        
        for point in all_points:
            # 2. Check if this point is inside any box
            found_box = None
            for box in boxes:
                if box.contains_point(point):
                    found_box = box
                    break
            
            # Only proceed if inside a box
            if found_box:
                points_inside_box += 1
                # self._log_debug(f"\n--- Searching in Box {found_box.id} at ({point.x:.1f}, {point.y:.1f}) ---")
                
                # 3. Search for pin label near this point
                label = self._find_label_near_point(point, text_engine)
                
                # Filter invalid labels (noise reduction)
                if label and self._is_valid_pin_label(label):
                    full_label = f"{found_box.id}:{label}"
                    
                    # Duplicate Check Logic:
                    # If same label exists but different location, we append a counter (e.g. "Pin (2)")
                    
                    is_same_location_duplicate = False
                    duplicate_count = 0
                    
                    for existing_pin in pins:
                        # Check if base label matches (ignoring existing suffixes if any, though here we compare raw labels mostly)
                        # Actually, let's compare the 'pin_label' field which is the raw text
                        if existing_pin['pin_label'] == label:
                            duplicate_count += 1
                            
                            # Check distance to see if it's the exact same physical pin scan
                            ex, ey = existing_pin['location']
                            import math
                            dist = math.sqrt((ex - point.x)**2 + (ey - point.y)**2)
                            
                            if dist < 10.0: 
                                is_same_location_duplicate = True
                                break
                    
                    if not is_same_location_duplicate:
                        # It's a new instance of the same label!
                        final_label = label
                        if duplicate_count > 0:
                            final_label = f"{label} ({duplicate_count + 1})"
                            
                        full_label = f"{found_box.id}:{final_label}"
                        
                        pin_info = {
                            'box_id': found_box.id,
                            'pin_label': label, # Keep raw label for future comparisons
                            'full_label': full_label,
                            'location': (point.x, point.y)
                        }
                        pins.append(pin_info)
                        logger.info(f"FOUND PIN: {full_label} at {point.x},{point.y}")
                        self._log_debug(f"✅ FOUND: {full_label}")
                    else:
                        # Same label at same location -> Ignore
                        pass 
                else:
                    # No valid label found
                    pass
        
        return pins

    def _is_valid_pin_label(self, label: str) -> bool:
        """
        Validates if a text is likely a pin number.
        """
        if not label: return False
        if len(label) > 6: return False 
        if label.startswith('/'): return False 
        if len(label) < 1: return False
        return True

    def _get_all_group_points(self, group) -> List[Any]:
        """
        Returns a list of ALL unique points in the wire network.
        """
        class SimplePoint:
            def __init__(self, x, y): self.x, self.y = x, y
            
        unique_points = set()
        result_points = []
        
        def normalize(val): return round(val, 2)

        for elem in group.elements:
            p1 = (normalize(elem.start_point.x), normalize(elem.start_point.y))
            p2 = (normalize(elem.end_point.x), normalize(elem.end_point.y))
            
            if p1 not in unique_points:
                unique_points.add(p1)
                result_points.append(SimplePoint(p1[0], p1[1]))
                
            if p2 not in unique_points:
                unique_points.add(p2)
                result_points.append(SimplePoint(p2[0], p2[1]))
                
        return result_points

    def _find_label_near_point(self, point, text_engine) -> Optional[str]:
        """
        Searches for text near the given point using the text engine.
        """
        # Create a search profile for pins
        profile = SearchProfile(
            search_radius=self.search_radius,
            direction=SearchDirection.ANY, 
            regex_pattern=r'^[a-zA-Z0-9\.\-\/]+$', 
            use_ocr_fallback=True
        )
        
        # DEBUG: Manually iterate all texts to see what's around
        best_text = None
        min_dist = float('inf')
        
        # Max distance to accept a label as "connected" to this point
        # Even if search radius is large, the label should be relatively close to the wire end.
        MAX_ACCEPTABLE_DISTANCE = 25.0 
        
        if hasattr(text_engine, 'pdf_elements'):
            import math
            for elem in text_engine.pdf_elements:
                dx = elem.center[0] - point.x
                dy = elem.center[1] - point.y
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist <= self.search_radius:
                    text = elem.text
                    # self._log_debug(f"   Candidate: '{text}' (dist: {dist:.1f})")
                    
                    import re
                    if re.match(profile.regex_pattern, text):
                        if dist < min_dist:
                            min_dist = dist
                            best_text = text
        
        if best_text and min_dist <= MAX_ACCEPTABLE_DISTANCE:
            return best_text
            
        return None
