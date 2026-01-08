"""
SVG-Erstellung und -Export.

Erstellt SVG-Dateien aus Analyseergebnissen mit konfigurierbaren Visualisierungsoptionen.
"""

import xml.etree.ElementTree as ET
import math
from typing import Optional
import cairosvg

from .models import VectorAnalysisResult, AnalysisConfig, ExportOptions, Point, BrokenConnection


def create_svg_from_analysis_result(analysis_result: VectorAnalysisResult, 
                                   config: AnalysisConfig,
                                   export_options: ExportOptions,
                                   output_file: str = "page_vectors.svg") -> str:
    """Erstellt SVG aus strukturierten Analyseergebnissen.
    
    Args:
        analysis_result: Analyseergebnisse
        config: Analyse-Konfiguration
        export_options: Export-Optionen
        output_file: Pfad zur Ausgabedatei
        
    Returns:
        Pfad zur erstellten SVG-Datei
    """
    page_info = analysis_result.page_info
    page_width = page_info.width
    page_height = page_info.height
    
    print(f"Erstelle SVG aus Analyseergebnissen...")
    print(f"  Strukturelle Gruppen: {len(analysis_result.structural_groups)}")
    print(f"  Text-ähnliche Gruppen: {len(analysis_result.text_like_groups)}")
    print(f"  Einzelelemente: {len(analysis_result.single_elements)}")
    print(f"  Unterbrochene Verbindungen: {len(analysis_result.broken_connections)}")
    
    # Erstelle SVG-Root
    svg_root = ET.Element("svg")
    svg_root.set("width", str(int(page_width)))
    svg_root.set("height", str(int(page_height)))
    svg_root.set("viewBox", f"0 0 {int(page_width)} {int(page_height)}")
    svg_root.set("xmlns", "http://www.w3.org/2000/svg")
    
    # Hintergrund
    if export_options.svg_background_color:
        bg_rect = ET.SubElement(svg_root, "rect")
        bg_rect.set("width", "100%")
        bg_rect.set("height", "100%")
        bg_rect.set("fill", export_options.svg_background_color)
    
    # Debug-Informationen als Kommentar
    if export_options.svg_show_debug_info:
        debug_text = f"""
        Vektoranalyse-Export - Seite: {page_info.page_number}
        Größe: {page_width:.1f} x {page_height:.1f}
        Elemente: {analysis_result.statistics.total_elements}
        Strukturelle Gruppen: {len(analysis_result.structural_groups)}
        """
        # Füge Debug-Info als Text-Element hinzu statt als Kommentar
        debug_elem = ET.SubElement(svg_root, "text")
        debug_elem.set("x", "10")
        debug_elem.set("y", "20")
        debug_elem.set("font-family", "monospace")
        debug_elem.set("font-size", "10")
        debug_elem.set("fill", "#666")
        debug_elem.text = debug_text.strip()
    
    # Zeichne strukturelle Gruppen (farbig)
    for group in analysis_result.structural_groups:
        _draw_structural_group(svg_root, group, config)
    
    # Zeichne text-ähnliche Gruppen (grau)
    for group in analysis_result.text_like_groups:
        _draw_text_like_group(svg_root, group, config)
    
    # Zeichne Einzelelemente (grau)
    for path_elem in analysis_result.single_elements:
        _draw_single_element(svg_root, path_elem, config)
    
    # Zeichne Lückenfüllungen für unterbrochene Linien
    gap_fills_drawn = _draw_gap_fills(svg_root, analysis_result.broken_connections, 
                                    analysis_result.structural_groups, config)
    
    print(f"Lückenfüllungen gezeichnet: {gap_fills_drawn}")
    
    # Gitter (optional)
    if export_options.svg_show_grid:
        _draw_grid(svg_root, page_width, page_height)
    
    # SVG-Datei schreiben
    tree = ET.ElementTree(svg_root)
    ET.indent(tree, space="  ", level=0)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"SVG-Datei wurde erstellt: {output_file}")
    
    return output_file


def _draw_structural_group(svg_root: ET.Element, group, config: AnalysisConfig):
    """Zeichnet eine strukturelle Gruppe in das SVG."""
    for path_elem in group.elements:
        path_element = ET.SubElement(svg_root, "path")
        path_element.set("d", path_elem.path_data)
        path_element.set("stroke", group.color)
        path_element.set("fill", "none")
        path_element.set("stroke-width", "1.2")
        path_element.set("stroke-linecap", "round")
        path_element.set("stroke-linejoin", "round")
    
    # Zeichne Kreise in der Gruppe
    for circle in group.circles:
        circle_element = ET.SubElement(svg_root, "circle")
        circle_element.set("cx", str(circle.center.x))
        circle_element.set("cy", str(circle.center.y))
        circle_element.set("r", str(circle.radius))
        circle_element.set("stroke", group.color)
        circle_element.set("fill", "none" if not circle.is_filled else group.color)
        circle_element.set("fill-opacity", "0.3" if circle.is_filled else "0")
        circle_element.set("stroke-width", "2.0")


def _draw_text_like_group(svg_root: ET.Element, group, config: AnalysisConfig):
    """Zeichnet eine text-ähnliche Gruppe in das SVG."""
    for path_elem in group.elements:
        path_element = ET.SubElement(svg_root, "path")
        path_element.set("d", path_elem.path_data)
        path_element.set("stroke", group.color)
        path_element.set("fill", "none")
        path_element.set("stroke-width", str(config.svg_stroke_width))
        path_element.set("stroke-linecap", "round")


def _draw_single_element(svg_root: ET.Element, path_elem, config: AnalysisConfig):
    """Zeichnet ein Einzelelement in das SVG."""
    path_element = ET.SubElement(svg_root, "path")
    path_element.set("d", path_elem.path_data)
    path_element.set("stroke", "#888888")  # Grau
    path_element.set("fill", "none")
    path_element.set("stroke-width", str(config.svg_stroke_width))
    path_element.set("stroke-linecap", "round")


def _draw_gap_fills(svg_root: ET.Element, broken_connections, structural_groups, config: AnalysisConfig) -> int:
    """Zeichnet Lückenfüllungen für unterbrochene Linien."""
    gap_fills_drawn = 0
    
    # Erstelle Mapping von Element-Index zu Gruppenfarbe
    element_to_color = {}
    for group in structural_groups:
        for elem in group.elements:
            element_to_color[elem.index] = group.color
    
    for connection in broken_connections:
        # Finde die Farbe der betroffenen strukturellen Gruppe
        connection_color = element_to_color.get(connection.path1_index)
        
        if connection_color:
            # Berechne Dicke als Vielfaches der Linienstärke
            thickness = config.svg_stroke_width * config.gap_fill_thickness_factor
            
            # Berechne Richtungsvektor und Normalvektor
            dx = connection.gap_end.x - connection.gap_start.x
            dy = connection.gap_end.y - connection.gap_start.y
            length = math.sqrt(dx*dx + dy*dy)
            
            if length > 0:
                # Normalisierte Richtung
                dir_x = dx / length
                dir_y = dy / length
                
                # Normalvektor (senkrecht zur Linie, 90° gedreht)
                norm_x = -dir_y
                norm_y = dir_x
                
                # Rechteck-Koordinaten berechnen (thickness/2 nach beiden Seiten)
                half_thickness = thickness / 2
                
                # Vier Eckpunkte des Rechtecks
                p1_x = connection.gap_start.x + norm_x * half_thickness
                p1_y = connection.gap_start.y + norm_y * half_thickness
                p2_x = connection.gap_start.x - norm_x * half_thickness
                p2_y = connection.gap_start.y - norm_y * half_thickness
                p3_x = connection.gap_end.x - norm_x * half_thickness
                p3_y = connection.gap_end.y - norm_y * half_thickness
                p4_x = connection.gap_end.x + norm_x * half_thickness
                p4_y = connection.gap_end.y + norm_y * half_thickness
                
                # Erstelle gefülltes Rechteck
                gap_rect = ET.SubElement(svg_root, "polygon")
                points = f"{p1_x},{p1_y} {p2_x},{p2_y} {p3_x},{p3_y} {p4_x},{p4_y}"
                gap_rect.set("points", points)
                gap_rect.set("fill", connection_color)
                gap_rect.set("fill-opacity", str(config.gap_fill_opacity))
                gap_rect.set("stroke", "none")
                gap_fills_drawn += 1
    
    return gap_fills_drawn


def _draw_grid(svg_root: ET.Element, page_width: float, page_height: float, grid_size: float = 50.0):
    """Zeichnet ein Hilfsgitter in das SVG."""
    grid_group = ET.SubElement(svg_root, "g")
    grid_group.set("stroke", "#e0e0e0")
    grid_group.set("stroke-width", "0.5")
    grid_group.set("opacity", "0.5")
    
    # Vertikale Linien
    x = 0
    while x <= page_width:
        line = ET.SubElement(grid_group, "line")
        line.set("x1", str(x))
        line.set("y1", "0")
        line.set("x2", str(x))
        line.set("y2", str(page_height))
        x += grid_size
    
    # Horizontale Linien
    y = 0
    while y <= page_height:
        line = ET.SubElement(grid_group, "line")
        line.set("x1", "0")
        line.set("y1", str(y))
        line.set("x2", str(page_width))
        line.set("y2", str(y))
        y += grid_size


def export_to_png(svg_file: str, png_file: str, config: AnalysisConfig, 
                  page_width: float, page_height: float) -> bool:
    """Exportiert SVG zu PNG mit hoher Auflösung.
    
    Args:
        svg_file: Pfad zur SVG-Datei
        png_file: Pfad zur PNG-Ausgabedatei
        config: Analyse-Konfiguration
        page_width: Seitenbreite in PDF-Einheiten
        page_height: Seitenhöhe in PDF-Einheiten
        
    Returns:
        True wenn erfolgreich, False bei Fehler
    """
    try:
        cairosvg.svg2png(
            url=svg_file,
            write_to=png_file,
            output_width=int(page_width * config.png_scale_factor),
            output_height=int(page_height * config.png_scale_factor)
        )
        print(f"🖼️  PNG erstellt: {png_file}")
        print(f"   Auflösung: {int(page_width * config.png_scale_factor)}x{int(page_height * config.png_scale_factor)} Pixel")
        return True
    except Exception as e:
        print(f"⚠️  PNG-Export fehlgeschlagen: {e}")
        return False


def create_svg_from_drawings_legacy(drawings, page_rect, circles, continuous_groups, 
                                   broken_connections, config: AnalysisConfig,
                                   output_file: str = "page_vectors.svg") -> str:
    """Legacy-Funktion für Kompatibilität mit dem ursprünglichen Code.
    
    Diese Funktion wird vom ursprünglichen Code aufgerufen und erstellt SVG 
    direkt aus den rohen Datenstrukturen.
    """
    print(f"Analysiere {len(drawings)} Zeichenelemente...")
    
    # Sammle verwendete Indizes
    used_indices = set()
    for group in continuous_groups:
        for item in group:
            used_indices.add(item['index'])
    
    # SVG-Root-Element erstellen
    svg_root = ET.Element("svg")
    svg_root.set("xmlns", "http://www.w3.org/2000/svg")
    svg_root.set("width", str(int(page_rect.width)))
    svg_root.set("height", str(int(page_rect.height)))
    svg_root.set("viewBox", f"0 0 {int(page_rect.width)} {int(page_rect.height)}")
    
    # Weißen Hintergrund hinzufügen
    background = ET.SubElement(svg_root, "rect")
    background.set("x", "0")
    background.set("y", "0")
    background.set("width", str(int(page_rect.width)))
    background.set("height", str(int(page_rect.height)))
    background.set("fill", "white")
    
    # Filtere und färbe strukturelle Gruppen
    structural_groups = []
    text_like_groups = []
    
    for group in continuous_groups:
        if len(group) > 1 and _has_long_straight_lines_legacy(group, config.min_line_length):
            structural_groups.append(group)
        elif len(group) >= config.min_text_like_group_size:
            text_like_groups.append(group)
    
    print(f"Strukturelle Gruppen (mit langen Geraden): {len(structural_groups)}")
    print(f"Text-ähnliche Gruppen (ohne lange Geraden): {len(text_like_groups)}")
    
    # Färbe strukturelle Gruppen
    colored_groups_count = 0
    for group_index, group in enumerate(structural_groups):
        from .geometry import get_pleasant_color
        color = get_pleasant_color(group_index, len(structural_groups))
        
        # Erstelle eine Gruppe für alle Elemente dieser kontinuierlichen Struktur
        svg_group = ET.SubElement(svg_root, "g")
        svg_group.set("stroke", color)
        svg_group.set("fill", "none")
        svg_group.set("stroke-width", str(config.gap_fill_stroke_width))
        
        for item in group:
            if 'path_data' in item:
                path_element = ET.SubElement(svg_group, "path")
                path_element.set("d", item['path_data'])
        
        colored_groups_count += 1
    
    # Füge text-ähnliche und einzelne Elemente in Grau hinzu
    _add_remaining_elements_legacy(svg_root, drawings, continuous_groups, used_indices, config)
    
    # Zeichne Lückenfüllungen
    gap_fills_drawn = _draw_gap_fills_legacy(svg_root, broken_connections, structural_groups, config)
    
    print(f"Strukturelle Gruppen (farbig): {colored_groups_count}")
    print(f"Lückenfüllungen gezeichnet: {gap_fills_drawn}")
    
    # SVG-Datei schreiben
    tree = ET.ElementTree(svg_root)
    ET.indent(tree, space="  ", level=0)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"SVG-Datei wurde erstellt: {output_file}")
    
    return output_file


def _has_long_straight_lines_legacy(group, min_length: float = 15.0) -> bool:
    """Legacy-Funktion: Prüft ob eine Gruppe längere Geraden enthält."""
    for item in group:
        if item['type'] != 'path' or 'path_data' not in item:
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
                    from .geometry import distance_between_points
                    line_length = distance_between_points(current_point, new_point)
                    if line_length >= min_length:
                        return True
                    
                    current_point = new_point
                    i += 3
                else:
                    break
            else:
                i += 1
    
    return False


def _add_remaining_elements_legacy(svg_root, drawings, continuous_groups, used_indices, config):
    """Legacy-Funktion: Fügt verbleibende Elemente in Grau hinzu."""
    # Einzelne Elemente aus Gruppen mit nur einem Element
    single_element_count = 0
    for group in continuous_groups:
        if len(group) == 1:
            item = group[0]
            if 'path_data' in item:
                path_element = ET.SubElement(svg_root, "path")
                path_element.set("d", item['path_data'])
                path_element.set("stroke", "#888888")  # Grau
                path_element.set("fill", "none")
                path_element.set("stroke-width", str(config.svg_stroke_width))
                single_element_count += 1
    
    # Text-ähnliche Gruppen (mehrteilig aber ohne lange Geraden)
    text_like_count = 0
    for group in continuous_groups:
        if len(group) > 1 and not _has_long_straight_lines_legacy(group, config.min_line_length):
            for item in group:
                if 'path_data' in item:
                    path_element = ET.SubElement(svg_root, "path")
                    path_element.set("d", item['path_data'])
                    path_element.set("stroke", "#888888")  # Grau
                    path_element.set("fill", "none")
                    path_element.set("stroke-width", str(config.svg_stroke_width))
                    text_like_count += 1
    
    print(f"Text-ähnliche Elemente (grau): {text_like_count}")
    print(f"Einzelelemente (grau): {single_element_count}")


def _draw_gap_fills_legacy(svg_root, broken_connections, structural_groups, config) -> int:
    """Legacy-Funktion: Zeichnet Lückenfüllungen."""
    gap_fills_drawn = 0
    
    # Erstelle Mapping von Element-Index zu Gruppenfarbe
    element_to_color = {}
    for group_idx, group in enumerate(structural_groups):
        from .geometry import get_pleasant_color
        color = get_pleasant_color(group_idx, len(structural_groups))
        for item in group:
            element_to_color[item['index']] = color
    
    for connection in broken_connections:
        # Finde die Farbe der Gruppe (wenn strukturell)
        path1_color = element_to_color.get(connection['path1_index'])
        path2_color = element_to_color.get(connection['path2_index'])
        
        # Verwende die Farbe wenn beide Pfade zur gleichen strukturellen Gruppe gehören
        if path1_color and path1_color == path2_color:
            gap_start = connection['gap_start']
            gap_end = connection['gap_end']
            
            # Extrahiere Koordinaten
            if hasattr(gap_start, 'x'):
                start_x, start_y = gap_start.x, gap_start.y
            else:
                start_x, start_y = gap_start[0], gap_start[1]
            
            if hasattr(gap_end, 'x'):
                end_x, end_y = gap_end.x, gap_end.y
            else:
                end_x, end_y = gap_end[0], gap_end[1]
            
            # Berechne Dicke als Vielfaches der Linienstärke
            thickness = config.svg_stroke_width * config.gap_fill_thickness_factor
            
            # Berechne Richtungsvektor und Normalvektor
            dx = end_x - start_x
            dy = end_y - start_y
            length = math.sqrt(dx*dx + dy*dy)
            
            if length > 0:
                # Normalisierte Richtung
                dir_x = dx / length
                dir_y = dy / length
                
                # Normalvektor (senkrecht zur Linie, 90° gedreht)
                norm_x = -dir_y
                norm_y = dir_x
                
                # Rechteck-Koordinaten berechnen (thickness/2 nach beiden Seiten)
                half_thickness = thickness / 2
                
                # Vier Eckpunkte des Rechtecks
                p1_x = start_x + norm_x * half_thickness
                p1_y = start_y + norm_y * half_thickness
                p2_x = start_x - norm_x * half_thickness
                p2_y = start_y - norm_y * half_thickness
                p3_x = end_x - norm_x * half_thickness
                p3_y = end_y - norm_y * half_thickness
                p4_x = end_x + norm_x * half_thickness
                p4_y = end_y + norm_y * half_thickness
                
                # Erstelle gefülltes Rechteck
                gap_rect = ET.SubElement(svg_root, "polygon")
                points = f"{p1_x},{p1_y} {p2_x},{p2_y} {p3_x},{p3_y} {p4_x},{p4_y}"
                gap_rect.set("points", points)
                gap_rect.set("fill", path1_color)
                gap_rect.set("fill-opacity", str(config.gap_fill_opacity))
                gap_rect.set("stroke", "none")
                gap_fills_drawn += 1
    
    return gap_fills_drawn