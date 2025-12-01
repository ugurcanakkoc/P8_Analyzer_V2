# Dosya: src/label_matcher.py

import math

class LabelMatcher:
    def __init__(self, page):
        """
        PyMuPDF page nesnesini alır ve sayfadaki tüm metinleri önbelleğe alır.
        """
        self.page = page
        self.text_blocks = self._extract_all_text()

    def _extract_all_text(self):
        """Sayfadaki tüm metin bloklarını ve koordinatlarını çıkarır."""
        text_data = []
        # "dict" formatı daha detaylı bilgi verir (bloklar, satırlar, spanlar)
        # Ancak basitlik için "words" kullanıp, yakın kelimeleri birleştirebiliriz.
        # Şimdilik "words" ile devam edelim, ancak birleştirme mantığı ekleyelim.
        
        words = self.page.get_text("words")
        # words formatı: (x0, y0, x1, y1, "kelime", block_no, line_no, word_no)
        
        for w in words:
            text = w[4]
            # Gereksiz kısa veya anlamsız metinleri eleyebiliriz
            if len(text.strip()) < 2: 
                continue
                
            text_dict = {
                'text': text,
                'bbox': (w[0], w[1], w[2], w[3]), # x0, y0, x1, y1
                'center': ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
            }
            text_data.append(text_dict)
        return text_data

    def _dist_point_to_rect(self, point, rect):
        """Bir nokta ile bir dikdörtgen (x0, y0, x1, y1) arasındaki en kısa mesafeyi hesaplar."""
        px, py = point
        rx0, ry0, rx1, ry1 = rect
        
        # Noktanın dikdörtgene göre konumu
        dx = max(rx0 - px, 0, px - rx1)
        dy = max(ry0 - py, 0, py - ry1)
        
        return math.hypot(dx, dy)

    def find_label_for_point(self, point, search_radius=50):
        """
        Verilen (x, y) noktasına search_radius içinde en yakın metni bulur.
        Mesafe hesabı bounding box'a göre yapılır.
        """
        closest_text = None
        min_dist = float('inf')

        for item in self.text_blocks:
            # Bounding box'a olan mesafeyi hesapla
            dist = self._dist_point_to_rect(point, item['bbox'])

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
        
        if not net_points:
            return []

        # Hattın başlangıç ve bitiş noktaları
        # net_points listesi [(x,y), (x,y), ...] şeklindedir.
        endpoints = [net_points[0], net_points[-1]]

        for ep in endpoints:
            if not self._is_inside_any_component(ep, components):
                # Bu uç boşta! Etiket ara.
                label = self.find_label_for_point(ep, search_radius)
                if label:
                    # Etiket bulundu, listeye ekle
                    found_labels.append(label)
        
        # Listeyi tekilleştir
        return list(set(found_labels))

    def _is_inside_any_component(self, point, components):
        """Bir noktanın herhangi bir kutu/klemens içinde olup olmadığına bakar."""
        px, py = point
        for comp in components:
            bbox = comp.bbox # {'min_x': ..., 'max_x': ...}
            # Toleranslı kontrol (biraz pay bırakabiliriz)
            margin = 2.0
            if (bbox['min_x'] - margin <= px <= bbox['max_x'] + margin and 
                bbox['min_y'] - margin <= py <= bbox['max_y'] + margin):
                return True
        return False

    def find_labels_in_rect(self, rect):
        """
        Belirtilen dikdörtgen alan (x0, y0, x1, y1) içinde kalan veya kesişen metinleri bulur.
        """
        found_texts = []
        rx0, ry0, rx1, ry1 = rect
        
        for item in self.text_blocks:
            tx0, ty0, tx1, ty1 = item['bbox']
            
            # Dikdörtgenlerin kesişim kontrolü (AABB intersection)
            if (rx0 < tx1 and rx1 > tx0 and
                ry0 < ty1 and ry1 > ty0):
                found_texts.append(item['text'])
                
        return found_texts