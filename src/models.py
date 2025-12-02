from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Tuple

# Point sınıfı koordinat işlemleri için temel yapı taşıdır
class Point(BaseModel):
    x: float
    y: float

class Circle(BaseModel):
    index: int
    center: Point
    radius: float
    coefficient_of_variation: float
    segments: int
    is_closed: bool
    is_filled: bool
    fill_color: Optional[str] = None
    drawing_data: Optional[Dict] = None

class PathElement(BaseModel):
    index: int
    type: str = "path"
    path_data: str
    start_point: Point
    end_point: Point
    length: Optional[float] = None
    direction_angle: Optional[float] = None

class StructuralGroup(BaseModel):
    group_id: int
    color: str
    elements: List[PathElement] = Field(default_factory=list)
    circles: List[Circle] = Field(default_factory=list)
    group_type: str = "structural"
    bounding_box: Optional[Dict[str, float]] = None

    def calculate_bounding_box(self) -> Dict[str, float]:
        if self.bounding_box is None:
            xs = [e.start_point.x for e in self.elements] + [e.end_point.x for e in self.elements]
            ys = [e.start_point.y for e in self.elements] + [e.end_point.y for e in self.elements]
            for c in self.circles:
                xs.extend([c.center.x - c.radius, c.center.x + c.radius])
                ys.extend([c.center.y - c.radius, c.center.y + c.radius])
            
            if xs and ys:
                self.bounding_box = {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys)}
            else:
                self.bounding_box = {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}
        return self.bounding_box

class PageInfo(BaseModel):
    page_number: int
    width: float
    height: float
    total_drawings: int

class AnalysisConfig(BaseModel):
    # Varsayılan ayarlar buradadır, worker bunları kullanır
    target_angle: float = 90.0
    gap_fill_stroke_width: float = 1.0
    png_scale_factor: float = 4.0
    # ... (Diğer ayarlar varsayılan değerleriyle kalabilir)

class VectorAnalysisResult(BaseModel):
    page_info: PageInfo
    structural_groups: List[StructuralGroup] = Field(default_factory=list)
    
    # --- KRİTİK EKLENTİ ---
    # Terminal analiz sonuçlarını saklamak için gerekli alan
    terminals: List[Dict[str, Any]] = Field(default_factory=list) 
    # ----------------------
    
    config: AnalysisConfig
    analysis_timestamp: Optional[str] = None

    # Gereksiz alanlar (single_elements, broken_connections vb.) 
    # eğer UI tarafında kullanılmıyorsa modelden çıkarılabilir veya boş bırakılabilir.
    # Şimdilik uyumluluk için tutuyoruz ama optional yapıyoruz.
    all_circles: List[Circle] = Field(default_factory=list)
    all_paths: List[PathElement] = Field(default_factory=list)