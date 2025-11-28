from dataclasses import dataclass
from typing import List, Dict, Any
from external.uvp.src.models import VectorAnalysisResult, Point

@dataclass
class CircuitComponent:
    """
    Kutuları temsil eden sınıf. 
    src/models.py dosyasını kirletmemek için burada tanımladık.
    """
    id: str
    label: str
    bbox: Dict[str, float]  # {min_x, min_y, max_x, max_y}
    
    def contains_point(self, point: Point, tolerance: float = 0.0) -> bool:
        return (self.bbox["min_x"] - tolerance <= point.x <= self.bbox["max_x"] + tolerance and
                self.bbox["min_y"] - tolerance <= point.y <= self.bbox["max_y"] + tolerance)

def check_intersections(components: List[CircuitComponent], 
                        analysis_result: VectorAnalysisResult) -> Dict[str, List[str]]:
    """
    Kutular (CircuitComponent) ile Hatlar (UVP StructuralGroups) arasındaki bağlantıları bulur.
    """
    connections_map = {} # Örn: { 'NET-001': ['BOX-1', 'BOX-2'] }
    
    # UVP'den gelen her bir hat grubu için
    for i, group in enumerate(analysis_result.structural_groups):
        
        # ID isimlendirmesini burada, sunum katmanında yapıyoruz
        net_name = f"NET-{i+1:03d}"
        
        connected_boxes = []
        
        # Hattın dokunduğu tüm noktaları topla
        points_to_check = []
        
        # 1. Çizgi uç noktaları
        for elem in group.elements:
            points_to_check.append(elem.start_point)
            points_to_check.append(elem.end_point)
            
        # 2. Daire merkezleri
        for circle in group.circles:
            points_to_check.append(circle.center)
            
        # Her bir kutu için kontrol et
        for comp in components:
            is_connected = False
            for p in points_to_check:
                # 5 birim tolerans ile çarpışma kontrolü
                if comp.contains_point(p, tolerance=5.0): 
                    is_connected = True
                    break
            
            if is_connected:
                connected_boxes.append(comp.id)
        
        # Eğer bu hat en az bir kutuya değiyorsa kaydet
        if connected_boxes:
            connections_map[net_name] = connected_boxes
            
    return connections_map