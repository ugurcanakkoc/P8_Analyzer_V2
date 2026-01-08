"""
Kreiserkennung und -analyse.

Analysiert Zeichenelemente auf kreisförmige Strukturen und erstellt Circle-Objekte.
"""

import math
from typing import List, Tuple, Dict, Any
from .models import Circle, Point, AnalysisConfig
from .geometry import distance_between_points


def extract_points_from_drawing(drawing: Dict[str, Any]) -> List[Point]:
    """Extrahiert alle Punkte aus einem Zeichenelement.
    
    Args:
        drawing: Zeichenelement mit items-Liste
        
    Returns:
        Liste von Point-Objekten
    """
    points = []
    items = drawing.get("items", [])
    
    for item in items:
        if item[0] == "l":  # line to
            points.extend([Point(x=item[1].x, y=item[1].y), Point(x=item[2].x, y=item[2].y)])
        elif item[0] == "m":  # move to
            points.append(Point(x=item[1].x, y=item[1].y))
        elif item[0] == "c":  # curve to
            points.extend([
                Point(x=item[1].x, y=item[1].y), 
                Point(x=item[2].x, y=item[2].y), 
                Point(x=item[3].x, y=item[3].y)
            ])
    
    return points


def calculate_circle_properties(points: List[Point]) -> Tuple[Point, float, float]:
    """Berechnet Zentrum, Radius und Variationskoeffizient für eine Punktmenge.
    
    Args:
        points: Liste von Punkten
        
    Returns:
        Tupel aus (Zentrum, durchschnittlicher Radius, Variationskoeffizient)
    """
    if not points:
        return Point(x=0, y=0), 0.0, float('inf')
    
    # Berechne Zentrum als Schwerpunkt
    center_x = sum(p.x for p in points) / len(points)
    center_y = sum(p.y for p in points) / len(points)
    center = Point(x=center_x, y=center_y)
    
    # Berechne Abstände zum Zentrum
    distances = [distance_between_points(center, p) for p in points]
    
    if not distances:
        return center, 0.0, float('inf')
    
    avg_radius = sum(distances) / len(distances)
    
    # Berechne Variationskoeffizient (Standardabweichung / Mittelwert)
    if avg_radius > 0:
        variance = sum((d - avg_radius)**2 for d in distances) / len(distances)
        coefficient_of_variation = math.sqrt(variance) / avg_radius
    else:
        coefficient_of_variation = float('inf')
    
    return center, avg_radius, coefficient_of_variation


def is_potential_circle(drawing: Dict[str, Any], config: AnalysisConfig) -> bool:
    """Prüft ob ein Zeichenelement potenziell ein Kreis ist.
    
    Args:
        drawing: Zeichenelement
        config: Analyse-Konfiguration
        
    Returns:
        True wenn es sich um einen potenziellen Kreis handelt
    """
    items = drawing.get("items", [])
    
    # Mindestanzahl von Segmenten für Kreiserkennung
    if len(items) < config.min_circle_segments:
        return False
    
    # Prüfe auf geschlossenen Pfad (oft ein Indikator für Kreise)
    is_closed = drawing.get("closePath", False)
    
    # Kreise haben oft viele kleine Segmente oder Kurven
    has_curves = any(item[0] in ["c", "v", "y"] for item in items)
    has_many_lines = len(items) >= config.min_circle_segments
    
    return is_closed or has_curves or has_many_lines


def analyze_circle_candidate(drawing: Dict[str, Any], index: int, config: AnalysisConfig) -> Circle:
    """Analysiert einen Kreis-Kandidaten und erstellt ein Circle-Objekt.
    
    Args:
        drawing: Zeichenelement
        index: Index des Elements
        config: Analyse-Konfiguration
        
    Returns:
        Circle-Objekt
    """
    points = extract_points_from_drawing(drawing)
    center, radius, coefficient_of_variation = calculate_circle_properties(points)
    
    # Weitere Eigenschaften des Zeichenelements
    is_closed = drawing.get("closePath", False)
    fill_info = drawing.get("fill", None)
    is_filled = fill_info is not None
    fill_color = None
    
    if is_filled and hasattr(fill_info, 'color'):
        fill_color = f"#{fill_info.color:06x}" if hasattr(fill_info, 'color') else None
    
    return Circle(
        index=index,
        center=center,
        radius=radius,
        coefficient_of_variation=coefficient_of_variation,
        segments=len(drawing.get("items", [])),
        is_closed=is_closed,
        is_filled=is_filled,
        fill_color=fill_color,
        drawing_data=None  # Entferne PyMuPDF-Objekte für JSON-Serialisierung
    )


def categorize_circles(circles: List[Circle], config: AnalysisConfig) -> Tuple[List[Circle], List[Circle]]:
    """Kategorisiert Kreise in definitive und potenzielle Kreise.
    
    Args:
        circles: Liste aller erkannten Kreise
        config: Analyse-Konfiguration
        
    Returns:
        Tupel aus (definitive Kreise, potenzielle Kreise)
    """
    definitive_circles = []
    potential_circles = []
    
    for circle in circles:
        if circle.coefficient_of_variation < config.strict_circle_cv_threshold:
            definitive_circles.append(circle)
        elif circle.coefficient_of_variation < config.circle_cv_threshold:
            potential_circles.append(circle)
    
    return definitive_circles, potential_circles


def analyze_circles_in_drawings(drawings: List[Dict[str, Any]], config: AnalysisConfig) -> Tuple[List[Circle], List[Circle]]:
    """Analysiert alle Zeichenelemente auf Kreise.
    
    Args:
        drawings: Liste aller Zeichenelemente
        config: Analyse-Konfiguration
        
    Returns:
        Tupel aus (definitive Kreise, potenzielle Kreise)
    """
    all_circles = []
    
    print(f"Analysiere {len(drawings)} Zeichenelemente auf Kreise...")
    
    for i, drawing in enumerate(drawings):
        if is_potential_circle(drawing, config):
            circle = analyze_circle_candidate(drawing, i, config)
            all_circles.append(circle)
    
    # Kategorisiere die Kreise
    definitive_circles, potential_circles = categorize_circles(all_circles, config)
    
    print(f"Kreise gefunden:")
    print(f"  Definitive Kreise: {len(definitive_circles)}")
    print(f"  Potenzielle Kreise: {len(potential_circles)}")
    
    if definitive_circles:
        filled_circles = sum(1 for c in definitive_circles if c.is_filled)
        unfilled_circles = len(definitive_circles) - filled_circles
        print(f"  Gefüllte Kreise: {filled_circles}")
        print(f"  Ungefüllte Kreise: {unfilled_circles}")
        
        print(f"  Kreisdetails (erste 10):")
        for i, circle in enumerate(definitive_circles[:10]):
            filled = "gefüllt" if circle.is_filled else "ungefüllt"
            print(f"    Kreis {i+1}: Radius {circle.radius:.1f}, {circle.segments} Segmente, {filled}, CV={circle.coefficient_of_variation:.3f}")
    
    return definitive_circles, potential_circles


def create_circle_path_data(circle: Circle) -> str:
    """Erstellt SVG-Pfad-Daten für einen Kreis.
    
    Args:
        circle: Circle-Objekt
        
    Returns:
        SVG-Pfad-String
    """
    center_x, center_y = circle.center.x, circle.center.y
    radius = circle.radius
    
    # Erstelle einen Kreis mit SVG-Pfad (zwei Halbkreise)
    return f"M {center_x - radius} {center_y} A {radius} {radius} 0 0 1 {center_x + radius} {center_y} A {radius} {radius} 0 0 1 {center_x - radius} {center_y} Z"


def find_circles_at_point(point, circles: List[Circle], tolerance: float = 3.0) -> List[Circle]:
    """Findet alle Kreise die einen gegebenen Punkt enthalten oder berühren.
    
    Args:
        point: Punkt zum Prüfen (Point-Objekt oder Tupel)
        circles: Liste von Circle-Objekten
        tolerance: Toleranz für die Punkterkennung
        
    Returns:
        Liste der Kreise die den Punkt enthalten
    """
    found_circles = []
    
    for circle in circles:
        if circle.contains_point(point, tolerance):
            found_circles.append(circle)
    
    return found_circles


def analyze_circle_connections(circles: List[Circle], paths: List[Dict], config: AnalysisConfig) -> Dict[str, List]:
    """Analysiert Verbindungen zwischen Kreisen und Pfaden.
    
    Args:
        circles: Liste von Circle-Objekten
        paths: Liste von Pfad-Elementen
        config: Analyse-Konfiguration
        
    Returns:
        Dictionary mit Verbindungsinformationen
    """
    connections = {
        'circle_to_circle': [],
        'circle_to_path': [],
        'isolated_circles': []
    }
    
    tolerance = config.circle_connection_tolerance
    
    # Finde Kreis-zu-Pfad Verbindungen
    for circle in circles:
        connected_paths = []
        
        for path in paths:
            # Prüfe beide Endpunkte des Pfades
            start_point = path.get('start')
            end_point = path.get('end')
            
            if start_point and circle.contains_point(start_point, tolerance):
                connected_paths.append(path)
            elif end_point and circle.contains_point(end_point, tolerance):
                connected_paths.append(path)
        
        if connected_paths:
            connections['circle_to_path'].append({
                'circle': circle,
                'connected_paths': connected_paths
            })
        else:
            connections['isolated_circles'].append(circle)
    
    # Finde Kreis-zu-Kreis Verbindungen (überlappende oder berührende Kreise)
    for i, circle1 in enumerate(circles):
        for j, circle2 in enumerate(circles[i+1:], i+1):
            center_distance = distance_between_points(circle1.center, circle2.center)
            combined_radius = circle1.radius + circle2.radius
            
            # Prüfe auf Berührung oder Überlappung
            if center_distance <= combined_radius + tolerance:
                connections['circle_to_circle'].append({
                    'circle1': circle1,
                    'circle2': circle2,
                    'distance': center_distance,
                    'type': 'overlapping' if center_distance < combined_radius else 'touching'
                })
    
    return connections