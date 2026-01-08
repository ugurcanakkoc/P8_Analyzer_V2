"""
Geometrische Berechnungen und Hilfsfunktionen.

Enthält alle mathematischen Operationen für Punkte, Linien, Winkel und Distanzen.
"""

import math
from typing import Tuple


def _extract_coordinates(point) -> Tuple[float, float]:
    """Hilfsfunktion zum Extrahieren von Koordinaten aus Point-Objekten oder Tupeln."""
    if hasattr(point, 'x') and hasattr(point, 'y'):
        return point.x, point.y
    else:
        return point[0], point[1]


def distance_between_points(p1, p2) -> float:
    """Berechnet die Distanz zwischen zwei Punkten.
    
    Args:
        p1: Erster Punkt (Point-Objekt oder Tupel)
        p2: Zweiter Punkt (Point-Objekt oder Tupel)
        
    Returns:
        Euklidische Distanz zwischen den Punkten
    """
    x1, y1 = _extract_coordinates(p1)
    x2, y2 = _extract_coordinates(p2)
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)


def calculate_vector_angle(p1, p2) -> float:
    """Berechnet den Winkel eines Vektors von p1 zu p2 in Grad.
    
    Args:
        p1: Startpunkt
        p2: Endpunkt
        
    Returns:
        Winkel in Grad (-180 bis 180)
    """
    x1, y1 = _extract_coordinates(p1)
    x2, y2 = _extract_coordinates(p2)
    
    dx = x2 - x1
    dy = y2 - y1
    return math.degrees(math.atan2(dy, dx))


def calculate_angle_between_vectors(v1_start, v1_end, v2_start, v2_end) -> float:
    """Berechnet den Winkel zwischen zwei Vektoren.
    
    Args:
        v1_start: Startpunkt des ersten Vektors
        v1_end: Endpunkt des ersten Vektors
        v2_start: Startpunkt des zweiten Vektors
        v2_end: Endpunkt des zweiten Vektors
        
    Returns:
        Winkel zwischen den Vektoren in Grad (0-180)
    """
    # Bestimme die Richtungsvektoren
    angle1 = calculate_vector_angle(v1_start, v1_end)
    angle2 = calculate_vector_angle(v2_start, v2_end)
    
    # Berechne die Differenz
    angle_diff = abs(angle1 - angle2)
    
    # Normalisiere auf 0-180 Grad
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    
    return angle_diff


def extend_line(start_point, end_point, extension_length: float) -> Tuple[float, float]:
    """Verlängert eine Linie um eine bestimmte Länge.
    
    Args:
        start_point: Startpunkt der Linie
        end_point: Endpunkt der Linie  
        extension_length: Länge der Verlängerung
        
    Returns:
        Neuer Endpunkt als Tupel (x, y)
    """
    x1, y1 = _extract_coordinates(start_point)
    x2, y2 = _extract_coordinates(end_point)
    
    dx = x2 - x1
    dy = y2 - y1
    
    # Normalisiere den Richtungsvektor
    length = math.sqrt(dx*dx + dy*dy)
    if length == 0:
        return (x2, y2)
    
    unit_x = dx / length
    unit_y = dy / length
    
    # Verlängere die Linie
    extended_x = x2 + unit_x * extension_length
    extended_y = y2 + unit_y * extension_length
    
    return (extended_x, extended_y)


def point_distance_to_line(point, line_start, line_end) -> float:
    """Berechnet den kürzesten Abstand eines Punktes zu einer Linie.
    
    Args:
        point: Punkt für den der Abstand berechnet wird
        line_start: Startpunkt der Linie
        line_end: Endpunkt der Linie
        
    Returns:
        Kürzester Abstand zur Linie
    """
    # Extrahiere Koordinaten
    if hasattr(point, 'x') and hasattr(point, 'y'):
        px, py = point.x, point.y
    else:
        px, py = point[0], point[1]
    
    if hasattr(line_start, 'x') and hasattr(line_start, 'y'):
        x1, y1 = line_start.x, line_start.y
    else:
        x1, y1 = line_start[0], line_start[1]
    
    if hasattr(line_end, 'x') and hasattr(line_end, 'y'):
        x2, y2 = line_end.x, line_end.y
    else:
        x2, y2 = line_end[0], line_end[1]
    
    A = px - x1
    B = py - y1
    C = x2 - x1
    D = y2 - y1
    
    dot = A * C + B * D
    len_sq = C * C + D * D
    
    if len_sq == 0:
        return distance_between_points(point, line_start)
    
    param = dot / len_sq
    
    if param < 0:
        xx = x1
        yy = y1
    elif param > 1:
        xx = x2
        yy = y2
    else:
        xx = x1 + param * C
        yy = y1 + param * D
    
    return distance_between_points(point, (xx, yy))


def are_lines_parallel(p1_start, p1_end, p2_start, p2_end, angle_tolerance: float = 5.0) -> bool:
    """Prüft ob zwei Linien parallel oder antiparallel verlaufen.
    
    Args:
        p1_start: Startpunkt der ersten Linie
        p1_end: Endpunkt der ersten Linie
        p2_start: Startpunkt der zweiten Linie
        p2_end: Endpunkt der zweiten Linie
        angle_tolerance: Toleranz für Winkelabweichung in Grad
        
    Returns:
        True wenn die Linien parallel sind
    """
    angle1 = calculate_vector_angle(p1_start, p1_end)
    angle2 = calculate_vector_angle(p2_start, p2_end)
    
    angle_diff = abs(angle1 - angle2)
    
    # Normalisiere auf 0-180 Grad
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    
    # Parallel (0°) oder antiparallel (180°)
    return angle_diff <= angle_tolerance or abs(angle_diff - 180) <= angle_tolerance


def is_perpendicular_connection(path1_start, path1_end, path2_start, path2_end,
                               connection_point, target_angle: float = 90.0, 
                               tolerance: float = 1.0) -> bool:
    """Prüft ob zwei Pfade sich in einem bestimmten Winkel treffen.
    
    Args:
        path1_start: Startpunkt des ersten Pfades
        path1_end: Endpunkt des ersten Pfades
        path2_start: Startpunkt des zweiten Pfades
        path2_end: Endpunkt des zweiten Pfades
        connection_point: Punkt der Verbindung
        target_angle: Zielwinkel in Grad
        tolerance: Toleranz für Winkelabweichung in Grad
        
    Returns:
        True wenn der Winkel innerhalb der Toleranz liegt
    """
    # Finde die Richtungsvektoren an der Verbindungsstelle
    v1_start, v1_end = None, None
    v2_start, v2_end = None, None
    
    # Bestimme Richtung von path1 zum Verbindungspunkt
    if distance_between_points(path1_start, connection_point) < distance_between_points(path1_end, connection_point):
        # Verbindung am Start von path1
        v1_start = path1_end
        v1_end = path1_start
    else:
        # Verbindung am Ende von path1
        v1_start = path1_start
        v1_end = path1_end
    
    # Bestimme Richtung von path2 zum Verbindungspunkt
    if distance_between_points(path2_start, connection_point) < distance_between_points(path2_end, connection_point):
        # Verbindung am Start von path2
        v2_start = path2_end
        v2_end = path2_start
    else:
        # Verbindung am Ende von path2
        v2_start = path2_start
        v2_end = path2_end
    
    # Berechne Winkel zwischen den Vektoren
    angle = calculate_angle_between_vectors(v1_start, v1_end, v2_start, v2_end)
    
    # Prüfe ob der Winkel nahe dem Zielwinkel liegt
    return abs(angle - target_angle) <= tolerance


def normalize_angle(angle: float) -> float:
    """Normalisiert einen Winkel auf den Bereich -180 bis 180 Grad.
    
    Args:
        angle: Winkel in Grad
        
    Returns:
        Normalisierter Winkel
    """
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360
    return angle


def calculate_line_length(start, end) -> float:
    """Berechnet die Länge einer Linie zwischen zwei Punkten.
    
    Args:
        start: Startpunkt
        end: Endpunkt
        
    Returns:
        Länge der Linie
    """
    return distance_between_points(start, end)


def midpoint(p1, p2) -> Tuple[float, float]:
    """Berechnet den Mittelpunkt zwischen zwei Punkten.
    
    Args:
        p1: Erster Punkt
        p2: Zweiter Punkt
        
    Returns:
        Mittelpunkt als Tupel (x, y)
    """
    # Extrahiere Koordinaten
    if hasattr(p1, 'x') and hasattr(p1, 'y'):
        x1, y1 = p1.x, p1.y
    else:
        x1, y1 = p1[0], p1[1]
    
    if hasattr(p2, 'x') and hasattr(p2, 'y'):
        x2, y2 = p2.x, p2.y
    else:
        x2, y2 = p2[0], p2[1]
    
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def get_pleasant_color(index: int, total_colors: int) -> str:
    """Generiert eine angenehme Farbe aus einem gleichmäßig verteilten Spektrum.
    
    Args:
        index: Index der Farbe (0-basiert)
        total_colors: Gesamtanzahl der Farben
        
    Returns:
        Hex-Farbcode (z.B. "#ff5733")
    """
    import colorsys
    
    # Verwende goldenen Schnitt für gleichmäßige Farbverteilung
    golden_ratio = 0.618033988749
    hue = (index * golden_ratio) % 1.0
    
    # Hohe Sättigung und mittlere Helligkeit für angenehme Farben
    saturation = 0.8
    value = 0.9
    
    rgb = colorsys.hsv_to_rgb(hue, saturation, value)
    
    # Konvertiere zu Hex
    return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"


def calculate_bounding_box(points: list) -> dict:
    """Berechnet die Bounding Box für eine Liste von Punkten.
    
    Args:
        points: Liste von Punkt-Objekten oder Tupeln
        
    Returns:
        Dictionary mit min_x, max_x, min_y, max_y
    """
    if not points:
        return {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}
    
    # Extrahiere alle x und y Koordinaten
    x_coords = []
    y_coords = []
    
    for point in points:
        if hasattr(point, 'x') and hasattr(point, 'y'):
            x_coords.append(point.x)
            y_coords.append(point.y)
        else:
            x_coords.append(point[0])
            y_coords.append(point[1])
    
    return {
        "min_x": min(x_coords),
        "max_x": max(x_coords),
        "min_y": min(y_coords),
        "max_y": max(y_coords)
    }