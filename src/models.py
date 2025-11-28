from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import json

class Point(BaseModel):
    """2D-Punkt mit x- und y-Koordinaten."""
    x: float
    y: float

class AnalysisConfig(BaseModel):
    target_angle: float = 90.0
    angle_tolerance: float = 1.0
    direction_tolerance: float = 5.0
    extension_length: float = 15.0
    line_tolerance: float = 0.5
    min_line_length: float = 10.0
    min_structural_group_size: int = 3
    min_text_like_group_size: int = 2
    connection_tolerance: float = 2.0
    circle_cv_threshold: float = 0.3
    strict_circle_cv_threshold: float = 0.1
    min_circle_segments: int = 8
    circle_connection_tolerance: float = 3.0
    svg_stroke_width: float = 0.6
    gap_fill_stroke_width: float = 1.0
    gap_fill_thickness_factor: float = 10.0
    gap_fill_opacity: float = 0.3
    png_scale_factor: float = 4.0

    def get_summary(self) -> str:
        return "Standard Config"

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

    def contains_point(self, point, tolerance: float = 0.0) -> bool:
        # Basit mesafe hesabı (import döngüsünü önlemek için buraya yazdık)
        px = point.x if hasattr(point, 'x') else point[0]
        py = point.y if hasattr(point, 'y') else point[1]
        dist = ((self.center.x - px)**2 + (self.center.y - py)**2)**0.5
        return dist <= self.radius + tolerance

class PathElement(BaseModel):
    index: int
    type: str = "path"
    path_data: str
    start_point: Point
    end_point: Point
    length: Optional[float] = None
    direction_angle: Optional[float] = None

class BrokenConnection(BaseModel):
    path1_index: int
    path2_index: int
    gap_start: Point
    gap_end: Point
    gap_length: float
    connection_type: str = "broken_line"

class StructuralGroup(BaseModel):
    group_id: int
    color: str
    elements: List[PathElement] = Field(default_factory=list)
    circles: List[Circle] = Field(default_factory=list)
    has_long_lines: bool = True
    group_type: str = "structural"
    total_length: Optional[float] = None
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
    area: Optional[float] = None

class AnalysisStatistics(BaseModel):
    total_elements: int
    total_circles: int
    total_paths: int
    structural_groups: int
    text_like_groups: int
    single_elements: int
    broken_connections: int
    total_groups: int
    definitive_circles: int = 0
    potential_circles: int = 0
    average_group_size: Optional[float] = None
    largest_group_size: int = 0
    total_path_length: Optional[float] = None
    coverage_ratio: Optional[float] = None

    def calculate_averages(self):
        pass

class VectorAnalysisResult(BaseModel):
    page_info: PageInfo
    all_circles: List[Circle] = Field(default_factory=list)
    all_paths: List[PathElement] = Field(default_factory=list)
    structural_groups: List[StructuralGroup] = Field(default_factory=list)
    text_like_groups: List[StructuralGroup] = Field(default_factory=list)
    single_elements: List[PathElement] = Field(default_factory=list)
    broken_connections: List[BrokenConnection] = Field(default_factory=list)
    statistics: AnalysisStatistics
    config: AnalysisConfig
    analysis_timestamp: Optional[str] = None

    def save_to_json(self, file_path: str):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.model_dump_json(indent=2))

class ExportOptions(BaseModel):
    create_svg: bool = True
    create_png: bool = True
    create_json: bool = True
    svg_background_color: str = "white"
    svg_show_grid: bool = False
    svg_show_debug_info: bool = False
    png_scale_factor: float = 4.0
    output_prefix: str = "page"
    include_timestamp: bool = False

DEFAULT_CONFIG = AnalysisConfig()