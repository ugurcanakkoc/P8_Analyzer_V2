# Dosya: gui/label_matcher.py (veya src/label_matcher.py)

import math

class LabelMatcher:
    def __init__(self, page):
        """
        PyMuPDF page nesnesini alır ve sayfadaki tüm metinleri önbelleğe alır.
        """
        self.page = page
        self.text_blocks = self._extract_all_text()

    def _extract_all_text(self):
        """Sayfadaki tüm kelimeleri ve koordinatlarını çıkarır."""
        text_data = []
        # "words" formatı: (x0, y0, x1, y1, "kelime", block_no, line_no, word_no)
        words = self.page.get_text("words")
        
        for w in words:
            text_dict = {
                'text': w[4],
                'bbox': (w[0], w[1], w[2], w[3]), # x0, y0, x1, y1
                'center': ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
            }
            text_data.append(text_dict)
        return text_data

    def find_label_for_point(self, point, search_radius=50):
        """
        Verilen (x, y) noktasına search_radius içinde en yakın metni bulur.
        point: (x, y) tuple
        search_radius: piksel cinsinden arama alanı
        """
        px, py = point
        closest_text = None
        min_dist = float('inf')

        for item in self.text_blocks:
            tx, ty = item['center']
            
            # Basit mesafe kontrolü (Euclidean)
            dist = math.hypot(px - tx, py - ty)

            if dist < search_radius:
                if dist < min_dist:
                    min_dist = dist
                    closest_text = item['text']

        return closest_text

    def find_labels_for_net(self, net_points, components, search_radius=40):
        """
        Bir hattın (net) uç noktalarını kontrol eder. 
        Eğer uç nokta bir kutu/klemens içinde değilse, etiket arar.
        """
        found_labels = []
        
        # Hattın başlangıç ve bitiş noktaları (polyline varsayımıyla)
        # net_points genellikle [(x,y), (x,y), ...] şeklindedir.
        endpoints = [net_points[0], net_points[-1]]

        for ep in endpoints:
            if not self._is_inside_any_component(ep, components):
                # Bu uç boşta! Etiket ara.
                label = self.find_label_for_point(ep, search_radius)
                if label:
                    found_labels.append(label)
        
        # Listeyi tekilleştir ve birleştir (örn: birden fazla kelime varsa)
        return list(set(found_labels))

    def _is_inside_any_component(self, point, components):
        """Bir noktanın herhangi bir kutu/klemens içinde olup olmadığına bakar."""
        px, py = point
        for comp in components:
            bbox = comp.bbox # {'min_x': ..., 'max_x': ...}
            if (bbox['min_x'] <= px <= bbox['max_x'] and 
                bbox['min_y'] <= py <= bbox['max_y']):
                return True
        return False