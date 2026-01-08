"""
Pfadanalyse und Gruppenerkennung.

Analysiert Pfadelemente, erkennt Verbindungen und gruppiert zusammengehörige Elemente.
"""

import math
from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict

from .models import PathElement, Point, BrokenConnection, StructuralGroup, AnalysisConfig, Circle, WireJunction, DetectedElement
from .geometry import (
    distance_between_points, 
    extend_line, 
    point_distance_to_line, 
    are_lines_parallel,
    is_perpendicular_connection,
    get_pleasant_color
)


def extract_path_endpoints(path_data: str) -> Tuple[Point, Point]:
    """Extrahiert Start- und Endpunkt eines SVG-Pfades.
    
    Args:
        path_data: SVG-Pfad-String
        
    Returns:
        Tupel aus (Startpunkt, Endpunkt)
    """
    commands = path_data.strip().split()
    
    start_point = None
    end_point = None
    current_point = None
    
    i = 0
    while i < len(commands):
        cmd = commands[i]
        
        if cmd == 'M':  # Move to
            if i + 2 < len(commands):
                x, y = float(commands[i+1]), float(commands[i+2])
                current_point = Point(x=x, y=y)
                if start_point is None:
                    start_point = current_point
                i += 3
            else:
                break
        elif cmd == 'L':  # Line to
            if i + 2 < len(commands):
                x, y = float(commands[i+1]), float(commands[i+2])
                current_point = Point(x=x, y=y)
                i += 3
            else:
                break
        elif cmd == 'C':  # Curve to
            if i + 6 < len(commands):
                # Für Kurven nehmen wir den letzten Kontrollpunkt
                x, y = float(commands[i+5]), float(commands[i+6])
                current_point = Point(x=x, y=y)
                i += 7
            else:
                break
        elif cmd == 'Z':  # Close path
            current_point = start_point
            i += 1
        else:
            i += 1
    
    end_point = current_point or start_point
    return start_point or Point(x=0, y=0), end_point or Point(x=0, y=0)


def create_path_data_from_drawing(drawing: Dict[str, Any]) -> str:
    """Erstellt SVG-Pfad-Daten aus einem Zeichenelement.
    
    Args:
        drawing: Zeichenelement mit items-Liste
        
    Returns:
        SVG-Pfad-String
    """
    path_data = []
    first_point = None
    
    for j, item in enumerate(drawing.get("items", [])):
        if item[0] == "l":  # line to
            if j == 0:  # Erstes Element
                first_point = item[1]
                path_data.append(f"M {item[1].x} {item[1].y}")
                path_data.append(f"L {item[2].x} {item[2].y}")
            else:
                path_data.append(f"L {item[2].x} {item[2].y}")
        elif item[0] == "m":  # move to
            path_data.append(f"M {item[1].x} {item[1].y}")
        elif item[0] == "c":  # curve to
            path_data.append(f"C {item[1].x} {item[1].y} {item[2].x} {item[2].y} {item[3].x} {item[3].y}")
        elif item[0] == "re":  # rectangle
            rect = item[1]
            path_data.append(f"M {rect.x0} {rect.y0}")
            path_data.append(f"L {rect.x1} {rect.y0}")
            path_data.append(f"L {rect.x1} {rect.y1}")
            path_data.append(f"L {rect.x0} {rect.y1}")
            path_data.append("Z")
        elif item[0] == "h":  # close path
            path_data.append("Z")
    
    return " ".join(path_data)


def extract_paths_from_drawings(drawings: List[Dict[str, Any]], circle_indices: Set[int]) -> List[PathElement]:
    """Extrahiert PathElement-Objekte aus Zeichenelementen (außer Kreise).
    
    Args:
        drawings: Liste aller Zeichenelemente
        circle_indices: Set der Indizes die Kreise repräsentieren
        
    Returns:
        Liste von PathElement-Objekten
    """
    paths = []
    
    for i, drawing in enumerate(drawings):
        if i in circle_indices:
            continue  # Kreise werden separat behandelt
            
        path_data = create_path_data_from_drawing(drawing)
        
        if path_data.strip():
            start_point, end_point = extract_path_endpoints(path_data)
            
            path_element = PathElement(
                index=i,
                type='path',
                path_data=path_data,
                start_point=start_point,
                end_point=end_point,
                length=None,  # Wird bei Bedarf berechnet
                direction_angle=None  # Wird bei Bedarf berechnet
            )
            paths.append(path_element)
    
    return paths


def find_broken_line_connections(paths: List[PathElement], config: AnalysisConfig) -> List[BrokenConnection]:
    """Findet unterbrochene Linienverbindungen zwischen Pfaden.
    
    Args:
        paths: Liste von PathElement-Objekten
        config: Analyse-Konfiguration
        
    Returns:
        Liste von BrokenConnection-Objekten
    """
    broken_connections = []
    
    print(f"Suche unterbrochene Linien (max. {config.extension_length} PDF-Einheiten Lücke)...")
    
    for i, path1 in enumerate(paths):
        for j, path2 in enumerate(paths):
            if i >= j:
                continue
            
            # Prüfe ob die Linien parallel sind
            if not are_lines_parallel(path1.start_point, path1.end_point, 
                                    path2.start_point, path2.end_point, 
                                    config.direction_tolerance):
                continue
            
            # Teste beide Richtungen für path1
            for path1_end, path1_other in [(path1.end_point, path1.start_point), 
                                          (path1.start_point, path1.end_point)]:
                # Verlängere path1
                extended_point = extend_line(path1_other, path1_end, config.extension_length)
                
                # Teste beide Endpunkte von path2
                for path2_start in [path2.start_point, path2.end_point]:
                    # Prüfe ob path2_start nahe der verlängerten Linie liegt
                    distance_to_line = point_distance_to_line(path2_start, path1_end, extended_point)
                    
                    if distance_to_line <= config.line_tolerance:
                        # Prüfe zusätzlich den direkten Abstand
                        direct_distance = distance_between_points(path1_end, path2_start)
                        if direct_distance <= config.extension_length:
                            broken_connections.append(BrokenConnection(
                                path1_index=path1.index,
                                path2_index=path2.index,
                                gap_start=path1_end,
                                gap_end=path2_start,
                                gap_length=direct_distance,
                                connection_type="broken_line"
                            ))
                            break
    
    print(f"Unterbrochene Linien gefunden: {len(broken_connections)}")
    return broken_connections


class UnionFind:
    """Union-Find Datenstruktur für effiziente Gruppierung."""
    
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
    
    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int):
        px, py = self.find(x), self.find(y)
        if px == py:
            return
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1


def trace_continuous_lines_with_circles(drawings: List[Dict[str, Any]], 
                                      circles: List[Circle], 
                                      config: AnalysisConfig) -> Tuple[List[List[Dict]], List[BrokenConnection]]:
    """Verfolgt kontinuierliche Linien durch die Zeichenelemente und verbindet sie über Kreise.
    
    Args:
        drawings: Liste aller Zeichenelemente
        circles: Liste der erkannten Kreise
        config: Analyse-Konfiguration
        
    Returns:
        Tupel aus (kontinuierliche Gruppen, unterbrochene Verbindungen)
    """
    print("Starte optimierte Pfad-Analyse...")
    
    # Sammle alle Pfade mit ihren Endpunkten (außer Kreise)
    circle_indices = set(c.index for c in circles)
    paths = extract_paths_from_drawings(drawings, circle_indices)
    
    print(f"Gefundene Pfade (ohne Kreise): {len(paths)}")
    
    # Konvertiere zu Dictionary-Format für Kompatibilität
    path_dicts = []
    for path in paths:
        path_dicts.append({
            'index': path.index,
            'path_data': path.path_data,
            'start': path.start_point,
            'end': path.end_point,
            'drawing': next((d for i, d in enumerate(drawings) if i == path.index), {}),
            'type': 'path'
        })
    
    # Erstelle Kreis-Dictionaries für Kompatibilität
    circle_dicts = []
    for circle in circles:
        circle_dicts.append({
            'index': circle.index,
            'type': 'circle',
            'center': circle.center,
            'drawing': next((d for i, d in enumerate(drawings) if i == circle.index), {}),
            'path_data': create_circle_path_data_from_circle(circle)
        })
    
    # Finde unterbrochene Linien
    broken_connections = find_broken_line_connections(paths, config)
    
    # Konvertiere zu Dictionary-Format für Rückgabe
    broken_connection_dicts = []
    for bc in broken_connections:
        broken_connection_dicts.append({
            'path1_index': bc.path1_index,
            'path2_index': bc.path2_index,
            'gap_start': bc.gap_start,
            'gap_end': bc.gap_end,
            'gap_length': bc.gap_length
        })
    
    # Erstelle Mappings für Union-Find
    all_elements = path_dicts + circle_dicts
    index_to_pos = {elem['index']: i for i, elem in enumerate(all_elements)}
    
    uf = UnionFind(len(all_elements))
    
    print("Analysiere Verbindungen...")
    print(f"Winkelprüfung: {config.target_angle}° ± {config.angle_tolerance}°")
    
    # Direkte Pfad-zu-Pfad Verbindungen mit Winkelprüfung
    direct_connections = 0
    angle_rejected = 0
    
    for i, path1_dict in enumerate(path_dicts):
        for j, path2_dict in enumerate(path_dicts):
            if i >= j:
                continue
            
            # Prüfe alle Kombinationen von Endpunkten
            points1 = [path1_dict['start'], path1_dict['end']]
            points2 = [path2_dict['start'], path2_dict['end']]
            
            connected = False
            for p1 in points1:
                for p2 in points2:
                    if distance_between_points(p1, p2) <= config.connection_tolerance:
                        # Prüfe zunächst, ob es verbindende Kreise gibt
                        circles_at_connection = find_circles_at_point(p1, circles, config.circle_connection_tolerance)
                        
                        if circles_at_connection:
                            # Wenn Kreise vorhanden sind, verbinde ohne Winkelprüfung
                            pos1 = index_to_pos[path1_dict['index']]
                            pos2 = index_to_pos[path2_dict['index']]
                            uf.union(pos1, pos2)
                            connected = True
                            direct_connections += 1
                        else:
                            # Keine Kreise - prüfe Winkel zwischen den Pfaden
                            if is_perpendicular_connection(
                                path1_dict['start'], path1_dict['end'],
                                path2_dict['start'], path2_dict['end'],
                                p1, config.target_angle, config.angle_tolerance):
                                pos1 = index_to_pos[path1_dict['index']]
                                pos2 = index_to_pos[path2_dict['index']]
                                uf.union(pos1, pos2)
                                connected = True
                                direct_connections += 1
                            else:
                                angle_rejected += 1
                        break
                if connected:
                    break
    
    print(f"Direkte Verbindungen: {direct_connections}, Winkel-abgelehnt: {angle_rejected}")
    
    # Verbinde unterbrochene Linien
    broken_line_connections = 0
    for connection in broken_connection_dicts:
        if connection['path1_index'] in index_to_pos and connection['path2_index'] in index_to_pos:
            pos1 = index_to_pos[connection['path1_index']]
            pos2 = index_to_pos[connection['path2_index']]
            uf.union(pos1, pos2)
            broken_line_connections += 1
    
    print(f"Unterbrochene Linien verbunden: {broken_line_connections}")
    
    # Pfad-zu-Kreis Verbindungen
    circle_connections = 0
    for path_dict in path_dicts:
        for point in [path_dict['start'], path_dict['end']]:
            connected_circles = find_circles_at_point(point, circles, config.circle_connection_tolerance)
            
            if connected_circles and path_dict['index'] in index_to_pos:
                path_pos = index_to_pos[path_dict['index']]
                for circle in connected_circles:
                    if circle.index in index_to_pos:
                        circle_pos = index_to_pos[circle.index]
                        uf.union(path_pos, circle_pos)
                        circle_connections += 1
    
    print(f"Pfad-zu-Kreis Verbindungen: {circle_connections}")
    
    # Gruppiere Elemente nach ihren Union-Find Gruppen
    groups = defaultdict(list)
    for i, elem in enumerate(all_elements):
        root = uf.find(i)
        groups[root].append(elem)
    
    continuous_groups = list(groups.values())
    
    print(f"Kontinuierliche Gruppen gefunden: {len(continuous_groups)}")
    group_sizes = [len(group) for group in continuous_groups]
    if group_sizes:
        print(f"Durchschnittliche Elemente pro Gruppe: {sum(group_sizes) / len(group_sizes):.1f}")
        print(f"Größte Gruppe: {max(group_sizes)} Elemente")
    
    # Debug: Zeige große Gruppen  
    large_groups = [g for g in continuous_groups if len(g) > 5]
    print(f"Große Gruppen (>5 Elemente): {len(large_groups)}")
    for i, group in enumerate(large_groups[:3]):  # Zeige erste 3 große Gruppen
        paths_in_group = sum(1 for item in group if item['type'] == 'path')
        circles_in_group = sum(1 for item in group if item['type'] == 'circle')
        print(f"  Gruppe {i+1}: {len(group)} Elemente ({paths_in_group} Pfade, {circles_in_group} Kreise)")
    
    return continuous_groups, broken_connection_dicts


def find_circles_at_point(point, circles: List[Circle], tolerance: float = 3.0) -> List[Circle]:
    """Findet alle Kreise die einen gegebenen Punkt enthalten."""
    found_circles = []
    for circle in circles:
        if circle.contains_point(point, tolerance):
            found_circles.append(circle)
    return found_circles


def create_circle_path_data_from_circle(circle: Circle) -> str:
    """Erstellt SVG-Pfad-Daten für einen Kreis."""
    center_x, center_y = circle.center.x, circle.center.y
    radius = circle.radius
    
    # Erstelle einen Kreis mit SVG-Pfad (zwei Halbkreise)
    return f"M {center_x - radius} {center_y} A {radius} {radius} 0 0 1 {center_x + radius} {center_y} A {radius} {radius} 0 0 1 {center_x - radius} {center_y} Z"


def has_long_straight_lines(group: List[Dict], config: AnalysisConfig) -> bool:
    """Prüft ob eine Gruppe längere Geraden enthält (um Buchstaben herauszufiltern).
    
    Args:
        group: Gruppe von Elementen
        config: Analyse-Konfiguration
        
    Returns:
        True wenn die Gruppe längere Geraden enthält
    """
    for item in group:
        if item['type'] != 'path':
            continue
            
        # Analysiere die Pfad-Daten auf längere Geraden
        path_data = item['path_data']
        commands = path_data.strip().split()
        
        current_point = None
        i = 0
        
        while i < len(commands):
            cmd = commands[i]
            
            if cmd == 'M':  # Move to
                if i + 2 < len(commands):
                    x, y = float(commands[i+1]), float(commands[i+2])
                    current_point = (x, y)
                    i += 3
                else:
                    break
            elif cmd == 'L':  # Line to
                if i + 2 < len(commands) and current_point:
                    x, y = float(commands[i+1]), float(commands[i+2])
                    new_point = (x, y)
                    
                    # Berechne Länge der Gerade
                    line_length = distance_between_points(current_point, new_point)
                    if line_length >= config.min_line_length:
                        return True
                    
                    current_point = new_point
                    i += 3
                else:
                    break
            else:
                i += 1
    
    return False


def categorize_groups(continuous_groups: List[List[Dict]], 
                     circles: List[Circle],
                     config: AnalysisConfig) -> Tuple[List[StructuralGroup], List[StructuralGroup], List[PathElement]]:
    """Kategorisiert Gruppen in strukturelle, text-ähnliche und Einzelelemente.
    
    Args:
        continuous_groups: Liste aller kontinuierlichen Gruppen
        circles: Liste aller erkannten Kreise
        config: Analyse-Konfiguration
        
    Returns:
        Tupel aus (strukturelle Gruppen, text-ähnliche Gruppen, Einzelelemente)
    """
    structural_groups = []
    text_like_groups = []
    single_elements = []
    
    for group_idx, group in enumerate(continuous_groups):
        # Konvertiere Gruppe zu PathElements und Circles
        group_paths = []
        group_circles = []
        
        for item in group:
            if item['type'] == 'path':
                path_elem = PathElement(
                    index=item['index'],
                    type='path',
                    path_data=item['path_data'],
                    start_point=item['start'],
                    end_point=item['end']
                )
                group_paths.append(path_elem)
            elif item['type'] == 'circle':
                # Finde das entsprechende Circle-Objekt aus der Liste
                circle_obj = next((c for c in circles if c.index == item['index']), None)
                if circle_obj:
                    group_circles.append(circle_obj)
        
        # Prüfe ob es eine strukturelle Gruppe ist
        if len(group) >= config.min_structural_group_size and has_long_straight_lines(group, config):
            color = get_pleasant_color(len(structural_groups), len(continuous_groups))
            structural_groups.append(StructuralGroup(
                group_id=len(structural_groups),
                color=color,
                elements=group_paths,
                circles=group_circles,
                has_long_lines=True,
                group_type="structural"
            ))
        elif len(group) >= config.min_text_like_group_size:
            text_like_groups.append(StructuralGroup(
                group_id=len(text_like_groups),
                color="#888888",  # Grau für text-ähnliche Gruppen
                elements=group_paths,
                circles=group_circles,
                has_long_lines=False,
                group_type="text_like"
            ))
        else:
            single_elements.extend(group_paths)

    return structural_groups, text_like_groups, single_elements


def find_wire_junctions(paths: List[PathElement], config: AnalysisConfig) -> List[WireJunction]:
    """Find points where 3 or more wires meet (T-junctions, crosses, etc.).

    Args:
        paths: List of PathElement objects
        config: Analysis configuration

    Returns:
        List of WireJunction objects
    """
    # Build a spatial index of all endpoints
    endpoint_map = defaultdict(list)
    tolerance = config.connection_tolerance

    for path in paths:
        # Round coordinates to create spatial buckets
        start_key = (round(path.start_point.x / tolerance) * tolerance,
                    round(path.start_point.y / tolerance) * tolerance)
        end_key = (round(path.end_point.x / tolerance) * tolerance,
                  round(path.end_point.y / tolerance) * tolerance)

        endpoint_map[start_key].append((path.index, path.start_point, 'start'))
        endpoint_map[end_key].append((path.index, path.end_point, 'end'))

    # Find junctions (points with 3+ wire endpoints)
    junctions = []
    processed_locations = set()

    for bucket_key, endpoints in endpoint_map.items():
        if len(endpoints) >= 3:  # At least 3 wires meeting
            # Calculate centroid of all endpoints in this bucket
            avg_x = sum(ep[1].x for ep in endpoints) / len(endpoints)
            avg_y = sum(ep[1].y for ep in endpoints) / len(endpoints)

            # Check if we've already processed a nearby junction
            location_key = (round(avg_x / (tolerance * 2)), round(avg_y / (tolerance * 2)))
            if location_key in processed_locations:
                continue
            processed_locations.add(location_key)

            # Determine junction type
            wire_count = len(endpoints)
            if wire_count == 3:
                junction_type = "t_junction"
            elif wire_count == 4:
                junction_type = "cross"
            else:
                junction_type = "multi_wire"

            junction = WireJunction(
                location=Point(x=avg_x, y=avg_y),
                wire_count=wire_count,
                connected_path_indices=[ep[0] for ep in endpoints],
                junction_type=junction_type
            )
            junctions.append(junction)

    print(f"Wire junctions found: {len(junctions)} (T: {sum(1 for j in junctions if j.junction_type == 't_junction')}, "
          f"Cross: {sum(1 for j in junctions if j.junction_type == 'cross')}, "
          f"Multi: {sum(1 for j in junctions if j.junction_type == 'multi_wire')})")

    return junctions


def create_detected_elements(
    broken_connections: List[BrokenConnection],
    wire_junctions: List[WireJunction],
    break_padding: float = 8.0,
    junction_size: float = 15.0
) -> List[DetectedElement]:
    """Convert broken connections and junctions to generic detected elements.

    Args:
        broken_connections: List of BrokenConnection objects
        wire_junctions: List of WireJunction objects
        break_padding: Padding around wire breaks for bounding box
        junction_size: Size of junction bounding boxes

    Returns:
        List of DetectedElement objects
    """
    elements = []
    element_id = 0

    # Convert broken connections to wire_break elements
    for bc in broken_connections:
        bbox = bc.get_bounding_box(padding=break_padding)

        # Expand small gaps to minimum visible size
        width = bbox["max_x"] - bbox["min_x"]
        height = bbox["max_y"] - bbox["min_y"]
        min_size = 12.0

        if width < min_size:
            expand = (min_size - width) / 2
            bbox["min_x"] -= expand
            bbox["max_x"] += expand
        if height < min_size:
            expand = (min_size - height) / 2
            bbox["min_y"] -= expand
            bbox["max_y"] += expand

        element = DetectedElement(
            element_id=element_id,
            element_type="wire_break",
            bounding_box=bbox,
            confidence=0.7,  # Medium confidence
            label=f"Break-{element_id+1}",
            source_data={
                "path1_index": bc.path1_index,
                "path2_index": bc.path2_index,
                "gap_length": bc.gap_length
            }
        )
        elements.append(element)
        element_id += 1

    # Convert junctions to junction elements
    for junc in wire_junctions:
        bbox = junc.get_bounding_box(size=junction_size)

        element = DetectedElement(
            element_id=element_id,
            element_type="junction",
            bounding_box=bbox,
            confidence=0.8 if junc.wire_count >= 4 else 0.6,
            label=f"Junc-{element_id+1} ({junc.wire_count})",
            source_data={
                "wire_count": junc.wire_count,
                "junction_type": junc.junction_type,
                "connected_paths": junc.connected_path_indices
            }
        )
        elements.append(element)
        element_id += 1

    print(f"Created {len(elements)} detected elements: "
          f"{sum(1 for e in elements if e.element_type == 'wire_break')} breaks, "
          f"{sum(1 for e in elements if e.element_type == 'junction')} junctions")

    return elements