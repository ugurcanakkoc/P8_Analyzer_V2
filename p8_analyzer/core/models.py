"""
Pydantic-Datenmodelle für die Vektoranalyse.

Definiert alle Datenstrukturen für Konfiguration, geometrische Objekte,
Analyseergebnisse und Exportoptionen.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
import json


class Point(BaseModel):
    """2D-Punkt mit x- und y-Koordinaten."""
    x: float
    y: float

    def __getitem__(self, index: int) -> float:
        """Ermöglicht Indexzugriff: point[0] für x, point[1] für y"""
        if index == 0:
            return self.x
        elif index == 1:
            return self.y
        else:
            raise IndexError("Point index out of range (0, 1)")


class AnalysisConfig(BaseModel):
    """Konfiguration für die Vektoranalyse mit allen Toleranz- und Schwellenwerten.
    
    Hinweis zu Einheiten:
    - PDF-Einheiten: 1 Einheit = 1/72 Zoll ≈ 0.35mm (Standard)
    - Bei einem A4-Dokument (595x842 PDF-Einheiten) entsprechen:
      * 15 PDF-Einheiten ≈ 5.3mm
      * 2 PDF-Einheiten ≈ 0.7mm
    """
    
    # Winkelprüfung
    target_angle: float = 90.0  # Zielwinkel in Grad für rechtwinklige Verbindungen
    angle_tolerance: float = 1.0  # Toleranz für Winkelabweichung in Grad
    direction_tolerance: float = 5.0  # Toleranz für Richtungswinkel bei unterbrochenen Linien
    
    # Linienerkennung
    extension_length: float = 15.0  # Maximale Lückenlänge für unterbrochene Linien in PDF-Einheiten
    line_tolerance: float = 0.5  # Toleranz für Linienausrichtung in PDF-Einheiten
    min_line_length: float = 10.0  # Mindestlänge für strukturelle Linien
    
    # Gruppierungskriterien
    min_structural_group_size: int = 3  # Mindestanzahl Elemente für strukturelle Gruppen
    min_text_like_group_size: int = 2  # Mindestanzahl Elemente für text-ähnliche Gruppen
    connection_tolerance: float = 2.0  # Toleranz für Punktverbindungen
    
    # Kreiserkennung
    circle_cv_threshold: float = 0.3  # Schwellenwert für Variationskoeffizient bei Kreiserkennung
    strict_circle_cv_threshold: float = 0.1  # Strenger Schwellenwert für definitive Kreise
    min_circle_segments: int = 8  # Mindestanzahl Segmente für Kreiserkennung
    circle_connection_tolerance: float = 3.0  # Toleranz für Kreis-Punkt-Verbindungen
    
    # SVG-Ausgabe
    svg_stroke_width: float = 0.6  # Linienstärke für SVG-Ausgabe in PDF-Einheiten
    gap_fill_stroke_width: float = 1.0  # Linienstärke für strukturelle Gruppen in PDF-Einheiten
    gap_fill_thickness_factor: float = 10.0  # Vielfaches der Linienstärke für Lückenfüllungen
    gap_fill_opacity: float = 0.3  # Transparenz der Lückenfüllungen (0.0-1.0)
    
    # PNG-Ausgabe
    png_scale_factor: float = 4.0  # Skalierungsfaktor für PNG-Ausgabe
    
    def get_summary(self) -> str:
        """Erstellt eine Zusammenfassung der aktuellen Konfiguration."""
        return f"""Analyse-Konfiguration:
  Winkelprüfung: {self.target_angle}° ± {self.angle_tolerance}°
  Max. Lückenlänge: {self.extension_length} PDF-Einheiten
  Linientoleranz: {self.line_tolerance} PDF-Einheiten
  Min. strukturelle Gruppe: {self.min_structural_group_size} Elemente
  Min. text-ähnliche Gruppe: {self.min_text_like_group_size} Elemente
  Kreis CV-Schwelle: {self.circle_cv_threshold}
  Min. Kreissegmente: {self.min_circle_segments}
  SVG Linienstärke: {self.svg_stroke_width} PDF-Einheiten
  Lückenfüllung: {self.gap_fill_thickness_factor}x Linienstärke, {self.gap_fill_opacity*100:.0f}% Deckkraft
  PNG Skalierung: {self.png_scale_factor}x"""


class Circle(BaseModel):
    """Erkannte Kreise mit geometrischen und visuellen Eigenschaften."""
    index: int
    center: Point
    radius: float
    coefficient_of_variation: float
    segments: int
    is_closed: bool
    is_filled: bool
    fill_color: Optional[str] = None
    drawing_data: Optional[Dict] = None  # Für PyMuPDF-Objekte (nicht serialisierbar)

    def contains_point(self, point, tolerance: float = 0.0) -> bool:
        """Prüft ob ein Punkt innerhalb des Kreises (plus Toleranz) liegt."""
        from .geometry import distance_between_points
        distance = distance_between_points(self.center, point)
        return distance <= self.radius + tolerance


class PathElement(BaseModel):
    """Pfadelement mit SVG-Daten und geometrischen Eigenschaften."""
    index: int
    type: str = "path"
    path_data: str
    start_point: Point
    end_point: Point
    length: Optional[float] = None
    direction_angle: Optional[float] = None

    def calculate_length(self) -> float:
        """Berechnet die Länge des Pfadelements."""
        if self.length is None:
            from .geometry import distance_between_points
            self.length = distance_between_points(self.start_point, self.end_point)
        return self.length or 0.0

    def calculate_direction_angle(self) -> float:
        """Berechnet den Richtungswinkel des Pfadelements."""
        if self.direction_angle is None:
            from .geometry import calculate_vector_angle
            self.direction_angle = calculate_vector_angle(self.start_point, self.end_point)
        return self.direction_angle or 0.0


class BrokenConnection(BaseModel):
    """Unterbrochene Linienverbindung zwischen zwei Pfadelementen."""
    path1_index: int
    path2_index: int
    gap_start: Point
    gap_end: Point
    gap_length: float
    connection_type: str = "broken_line"  # Typ der Verbindung

    def get_bounding_box(self, padding: float = 5.0) -> Dict[str, float]:
        """Calculate bounding box around the gap with optional padding."""
        min_x = min(self.gap_start.x, self.gap_end.x) - padding
        max_x = max(self.gap_start.x, self.gap_end.x) + padding
        min_y = min(self.gap_start.y, self.gap_end.y) - padding
        max_y = max(self.gap_start.y, self.gap_end.y) + padding
        return {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y}


class WireJunction(BaseModel):
    """Wire junction point where 3+ wires meet."""
    location: Point
    wire_count: int  # Number of wires meeting at this point
    connected_path_indices: List[int] = Field(default_factory=list)
    junction_type: str = "multi_wire"  # "multi_wire", "t_junction", "cross"

    def get_bounding_box(self, size: float = 10.0) -> Dict[str, float]:
        """Calculate bounding box around the junction point."""
        return {
            "min_x": self.location.x - size/2,
            "max_x": self.location.x + size/2,
            "min_y": self.location.y - size/2,
            "max_y": self.location.y + size/2
        }


class DetectedElement(BaseModel):
    """Generic detected circuit element with bounding box."""
    element_id: int
    element_type: str  # "wire_break", "junction", "component"
    bounding_box: Dict[str, float]
    confidence: float = 0.5
    label: Optional[str] = None
    source_data: Optional[Dict[str, Any]] = None

    def get_center(self) -> Point:
        """Get center point of bounding box."""
        cx = (self.bounding_box["min_x"] + self.bounding_box["max_x"]) / 2
        cy = (self.bounding_box["min_y"] + self.bounding_box["max_y"]) / 2
        return Point(x=cx, y=cy)


class StructuralGroup(BaseModel):
    """Strukturelle Gruppe von verbundenen Elementen."""
    group_id: int
    color: str
    elements: List[PathElement] = Field(default_factory=list)
    circles: List[Circle] = Field(default_factory=list)
    has_long_lines: bool = True
    group_type: str = "structural"  # "structural", "text_like", "single"
    total_length: Optional[float] = None
    bounding_box: Optional[Dict[str, float]] = None

    def calculate_total_length(self) -> float:
        """Berechnet die Gesamtlänge aller Pfadelemente in der Gruppe."""
        if self.total_length is None:
            self.total_length = sum(elem.calculate_length() for elem in self.elements)
        return self.total_length

    def calculate_bounding_box(self) -> Dict[str, float]:
        """Berechnet die Bounding Box der Gruppe."""
        if self.bounding_box is None and (self.elements or self.circles):
            all_points = []
            
            # Sammle alle Punkte der Pfadelemente
            for elem in self.elements:
                all_points.extend([elem.start_point, elem.end_point])
            
            # Sammle Kreispunkte (Randpunkte)
            for circle in self.circles:
                center = circle.center
                radius = circle.radius
                all_points.extend([
                    Point(x=center.x - radius, y=center.y - radius),
                    Point(x=center.x + radius, y=center.y + radius)
                ])
            
            if all_points:
                self.bounding_box = {
                    "min_x": min(p.x for p in all_points),
                    "max_x": max(p.x for p in all_points),
                    "min_y": min(p.y for p in all_points),
                    "max_y": max(p.y for p in all_points)
                }
        
        return self.bounding_box or {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}


class PageInfo(BaseModel):
    """Seiteninformationen für die Analyse."""
    page_number: int
    width: float
    height: float
    total_drawings: int
    area: Optional[float] = None

    def calculate_area(self) -> float:
        """Berechnet die Seitenfläche."""
        if self.area is None:
            self.area = self.width * self.height
        return self.area


class AnalysisStatistics(BaseModel):
    """Detaillierte Statistiken der Vektoranalyse."""
    total_elements: int
    total_circles: int
    total_paths: int
    structural_groups: int
    text_like_groups: int
    single_elements: int
    broken_connections: int
    total_groups: int
    
    # Erweiterte Statistiken
    definitive_circles: int = 0
    potential_circles: int = 0
    average_group_size: Optional[float] = None
    largest_group_size: int = 0
    total_path_length: Optional[float] = None
    coverage_ratio: Optional[float] = None  # Verhältnis erkannter zu gesamten Elementen

    def calculate_averages(self):
        """Berechnet Durchschnittswerte."""
        if self.total_groups > 0:
            self.average_group_size = (self.structural_groups + self.text_like_groups) / self.total_groups


class VectorAnalysisResult(BaseModel):
    """Hauptdatenstruktur für Vektoranalyse-Ergebnisse."""
    page_info: PageInfo
    
    # Erkannte Elemente
    all_circles: List[Circle] = Field(default_factory=list)
    all_paths: List[PathElement] = Field(default_factory=list)
    
    # Gruppierungen
    structural_groups: List[StructuralGroup] = Field(default_factory=list)
    text_like_groups: List[StructuralGroup] = Field(default_factory=list)
    single_elements: List[PathElement] = Field(default_factory=list)
    
    # Verbindungen
    broken_connections: List[BrokenConnection] = Field(default_factory=list)

    # Detected circuit elements (wire breaks, junctions)
    wire_junctions: List['WireJunction'] = Field(default_factory=list)
    detected_elements: List['DetectedElement'] = Field(default_factory=list)

    # Terminal detection results
    terminals: Optional[List[Any]] = None

    # Cluster-based component detection results
    component_clusters: Optional[List[Any]] = None
    cluster_labels: Optional[List[Any]] = None
    cluster_gap_fills: Optional[List[Any]] = None
    cluster_circle_pins: Optional[List[Any]] = None
    cluster_line_ends: Optional[List[Any]] = None

    # Statistiken und Metadaten
    statistics: AnalysisStatistics
    config: AnalysisConfig
    analysis_timestamp: Optional[str] = None
    
    def save_to_json(self, file_path: str):
        """Speichert die Analyse als JSON-Datei."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.model_dump_json(indent=2))
    
    @classmethod
    def load_from_json(cls, file_path: str) -> 'VectorAnalysisResult':
        """Lädt eine Analyse aus JSON-Datei."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.model_validate(data)

    def get_summary(self) -> str:
        """Erstellt eine Zusammenfassung der Analyseergebnisse."""
        stats = self.statistics
        return f"""Vektoranalyse-Zusammenfassung (Seite {self.page_info.page_number}):
  [Page] Seitengröße: {self.page_info.width:.1f} x {self.page_info.height:.1f}
  [Total] Gesamtelemente: {stats.total_elements}

  [Groups] Gruppierungen:
    - Strukturelle Gruppen: {stats.structural_groups}
    - Text-ähnliche Gruppen: {stats.text_like_groups}
    - Einzelelemente: {stats.single_elements}

  [Connections] Verbindungen:
    - Unterbrochene Linien: {stats.broken_connections}

  [Circles] Kreise:
    - Definitive Kreise: {stats.definitive_circles}
    - Mögliche Kreise: {stats.potential_circles}

  [Stats] Durchschnittliche Gruppengröße: {stats.average_group_size or 0:.1f}
  [Stats] Größte Gruppe: {stats.largest_group_size} Elemente"""


class ExportOptions(BaseModel):
    """Optionen für den Export von Analyseergebnissen."""
    create_svg: bool = True
    create_png: bool = True
    create_json: bool = True
    
    # SVG-spezifische Optionen
    svg_background_color: str = "white"
    svg_show_grid: bool = False
    svg_show_debug_info: bool = False
    
    # PNG-spezifische Optionen  
    png_dpi: Optional[int] = None
    png_quality: int = 95
    
    # Dateinamen
    output_prefix: str = "page"
    include_timestamp: bool = False


# Globale Standard-Konfiguration
DEFAULT_CONFIG = AnalysisConfig()