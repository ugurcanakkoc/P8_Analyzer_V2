import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class BusbarFinder:
    def __init__(self, matcher):
        self.matcher = matcher
        # Yataylık toleransı
        self.horizontal_tolerance = 2.0 

    def find_busbars(self, structural_groups, page_width, manual_boxes, viewer=None) -> Dict[str, str]:
        busbar_map = {}
        
        # Debug renkleri
        debug_colors = ["orange", "yellow", "cyan", "magenta", "lime", "blue"]
        color_idx = 0

        for i, group in enumerate(structural_groups):
            net_id = f"NET-{i+1:03d}"
            
            # 1. En soldaki yatay parçayı bul
            start_segment = self._find_leftmost_horizontal_segment(group)
            
            if not start_segment:
                continue
                
            seg_start_x, seg_y, length = start_segment
            
            # 2. Uzunluk Filtresi (Sayfanın %5'i)
            bbox = group.calculate_bounding_box()
            total_width = bbox['max_x'] - bbox['min_x']
            if total_width < page_width * 0.05:
                continue

            # 3. Kutu Kenarı Filtresi
            if self._is_line_part_of_box_border(seg_y, manual_boxes):
                continue

            # 4. KOORDİNATLAR
            target_x = seg_start_x
            target_y = seg_y
            
            # --- ÖLÇÜLER (Hafif revize edildi) ---
            # Aşağıya (target_y + X) payını neredeyse sıfırladım ki alttaki hatta bulaşmasın.
            search_rect = (
                target_x - 5,    
                target_y - 30,   # Yukarı 30px
                target_x + 150,  # Sağa 150px (Yazı uzunluğunu kapsasın)
                target_y + 2     # Aşağı SADECE 2px (Çizgi kalınlığı kadar, altına bakma)
            )
            # -------------------------------------

            current_color = debug_colors[color_idx % len(debug_colors)]
            color_idx += 1
            
            # --- GÖRSELLEŞTİRME ---
            if viewer:
                from PyQt5.QtGui import QColor
                viewer.draw_debug_point(
                    (target_x, target_y), 
                    color=QColor(current_color), 
                    radius=6.0
                )
                viewer.draw_debug_rect(search_rect, color=QColor(current_color), label=f"Scan")

            # 5. ETİKET ARAMA (Mesafe öncelikli)
            # target_y parametresini gönderiyoruz ki mesafeyi ölçebilsin
            label = self._find_label_in_area(search_rect, manual_boxes, target_line_y=target_y)
            
            if label:
                busbar_map[net_id] = label
                if viewer:
                    viewer.draw_debug_rect(search_rect, color=QColor("green"), label=f"OK: {label}")

        return busbar_map

    def _find_leftmost_horizontal_segment(self, group):
        candidates = []
        for elem in group.elements:
            y1 = elem.start_point.y
            y2 = elem.end_point.y
            
            if abs(y1 - y2) < self.horizontal_tolerance:
                x_start = min(elem.start_point.x, elem.end_point.x)
                x_end = max(elem.start_point.x, elem.end_point.x)
                y = (y1 + y2) / 2
                length = x_end - x_start
                candidates.append((x_start, y, length))
        
        if not candidates:
            return None
        
        # En soldakini döndür
        leftmost = sorted(candidates, key=lambda c: c[0])[0]
        return leftmost

    def _is_line_part_of_box_border(self, line_y, boxes):
        tolerance = 5.0
        for box in boxes:
            top_y = box.bbox['min_y']
            bottom_y = box.bbox['max_y']
            if abs(line_y - top_y) < tolerance or abs(line_y - bottom_y) < tolerance:
                return True
        return False

    def _find_label_in_area(self, rect, manual_boxes, target_line_y: float) -> Optional[str]:
        """
        Belirtilen alandaki en uygun etiketi bulur.
        YENİLİK: target_line_y'ye en yakın olanı seçer.
        """
        if not self.matcher: return None

        text_objects = self.matcher.find_text_objects_in_rect(rect)
        if not text_objects: return None
            
        candidates = [] # (mesafe, metin) saklayacak
        
        valid_starts = ("P", "N", "PE", "L", "M", "+", "-")
        valid_substrings = ("24V", "0V", "GND", "VCC", "DC")

        for obj in text_objects:
            text = obj['text'].strip()
            
            # Filtrelemeler
            if text.startswith("/") and any(c.isdigit() for c in text): continue
            
            center = obj['center']
            if self._is_inside_manual_box(center, manual_boxes): continue

            # Temizlik
            clean_text = text.split('/')[-1] if '/' in text else text
            
            # Geçerlilik Kontrolü
            if (clean_text.startswith(valid_starts) or 
                any(sub in clean_text for sub in valid_substrings)):
                
                # --- MESAFE HESABI ---
                # Metnin merkezi ile Hattın Y koordinatı arasındaki fark
                text_y = center[1]
                distance = abs(text_y - target_line_y)
                
                candidates.append((distance, clean_text))

        if candidates:
            # Mesafeye göre sırala (En küçük mesafe en üstte)
            # Böylece hatta en yakın olan yazı seçilir.
            candidates.sort(key=lambda x: x[0])
            
            # En yakın adayı döndür
            return candidates[0][1]
            
        return None

    def _is_inside_manual_box(self, point, boxes):
        px, py = point
        for box in boxes:
             if (box.bbox['min_x'] <= px <= box.bbox['max_x'] and
                 box.bbox['min_y'] <= py <= box.bbox['max_y']):
                 return True
        return False