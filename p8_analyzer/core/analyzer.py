"""
Hauptanalyse-Koordinator.

Koordiniert alle Analysemodule und erstellt strukturierte Ergebnisse.
"""

from datetime import datetime
from typing import List, Dict, Any, Tuple

from .models import (
    VectorAnalysisResult,
    AnalysisConfig,
    ExportOptions,
    PageInfo,
    AnalysisStatistics,
    Point,
    PathElement,
    Circle,
    BrokenConnection,
    StructuralGroup,
    WireJunction,
    DetectedElement
)
from .circle_analysis import analyze_circles_in_drawings
from .path_analysis import (
    trace_continuous_lines_with_circles,
    categorize_groups,
    extract_paths_from_drawings,
    find_wire_junctions,
    create_detected_elements
)
from .svg_export import create_svg_from_analysis_result, export_to_png


def analyze_page_vectors(drawings: List[Dict[str, Any]], 
                        page_rect,
                        page_number: int,
                        config: AnalysisConfig) -> VectorAnalysisResult:
    """Führt eine vollständige Vektoranalyse einer PDF-Seite durch.
    
    Args:
        drawings: Liste aller Zeichenelemente der Seite
        page_rect: PyMuPDF-Rechteck der Seite
        page_number: Seitennummer
        config: Analyse-Konfiguration
        
    Returns:
        Vollständiges VectorAnalysisResult-Objekt
    """
    print(f"Starte Vektoranalyse für Seite {page_number}...")
    print(f"Analysiere {len(drawings)} Zeichenelemente...")
    
    # 1. Seiteninformationen erstellen
    page_info = PageInfo(
        page_number=page_number,
        width=float(page_rect.width),
        height=float(page_rect.height),
        total_drawings=len(drawings)
    )
    
    # 2. Kreiserkennung
    print("Phase 1: Kreiserkennung...")
    definitive_circles, potential_circles = analyze_circles_in_drawings(drawings, config)
    all_circles = definitive_circles + potential_circles
    
    # 3. Pfadanalyse und Gruppierung
    print("Phase 2: Pfadanalyse und Gruppierung...")
    continuous_groups, broken_connections_dict = trace_continuous_lines_with_circles(
        drawings, definitive_circles, config
    )
    
    # 4. Konvertiere broken_connections zu Pydantic-Modellen
    broken_connections = []
    for conn_item in broken_connections_dict:
        if isinstance(conn_item, BrokenConnection):
            broken_connections.append(conn_item)
        else:
            # Legacy-Dictionary-Format
            broken_connections.append(BrokenConnection(
                path1_index=conn_item['path1_index'],
                path2_index=conn_item['path2_index'],
                gap_start=_ensure_point(conn_item['gap_start']),
                gap_end=_ensure_point(conn_item['gap_end']),
                gap_length=conn_item['gap_length'],
                connection_type="broken_line"
            ))
    
    # 5. Kategorisiere Gruppen
    print("Phase 3: Gruppenkategorisierung...")
    structural_groups, text_like_groups, single_elements = categorize_groups(
        continuous_groups, all_circles, config
    )
    
    # 6. Alle Pfadelemente sammeln
    circle_indices = set(c.index for c in all_circles)
    all_paths = extract_paths_from_drawings(drawings, circle_indices)

    # 7. Wire junction detection
    print("Phase 4: Wire junction detection...")
    wire_junctions = find_wire_junctions(all_paths, config)

    # 8. Create detected elements (wire breaks + junctions)
    print("Phase 5: Creating detected elements...")
    detected_elements = create_detected_elements(broken_connections, wire_junctions)

    # 9. Statistiken berechnen
    statistics = _calculate_statistics(
        drawings, all_circles, all_paths, definitive_circles, potential_circles,
        structural_groups, text_like_groups, single_elements, broken_connections,
        continuous_groups
    )

    # 10. Analyseergebnis zusammenstellen
    analysis_result = VectorAnalysisResult(
        page_info=page_info,
        all_circles=all_circles,
        all_paths=all_paths,
        structural_groups=structural_groups,
        text_like_groups=text_like_groups,
        single_elements=single_elements,
        broken_connections=broken_connections,
        wire_junctions=wire_junctions,
        detected_elements=detected_elements,
        statistics=statistics,
        config=config,
        analysis_timestamp=datetime.now().isoformat()
    )
    
    print("Analyse abgeschlossen:")
    print(analysis_result.get_summary())
    
    return analysis_result


def export_analysis_results(analysis_result: VectorAnalysisResult,
                          config: AnalysisConfig,
                          export_options: ExportOptions,
                          output_prefix: str = "page") -> Dict[str, str]:
    """Exportiert Analyseergebnisse in verschiedene Formate.
    
    Args:
        analysis_result: Analyseergebnisse
        config: Analyse-Konfiguration
        export_options: Export-Optionen
        output_prefix: Präfix für Ausgabedateien
        
    Returns:
        Dictionary mit Pfaden zu erstellten Dateien
    """
    page_number = analysis_result.page_info.page_number
    output_files = {}
    
    # Dateinamen erstellen
    if export_options.include_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{output_prefix}{page_number}_{timestamp}"
    else:
        base_name = f"{output_prefix}{page_number}"
    
    print(f"Exportiere Analyseergebnisse mit Präfix '{base_name}'...")
    
    # JSON-Export
    if export_options.create_json:
        json_file = f"{base_name}_analysis.json"
        analysis_result.save_to_json(json_file)
        output_files['json'] = json_file
        print(f"📄 JSON-Analyse: {json_file}")
    
    # SVG-Export
    if export_options.create_svg:
        svg_file = f"{base_name}_vectors.svg"
        create_svg_from_analysis_result(analysis_result, config, export_options, svg_file)
        output_files['svg'] = svg_file
    
    # PNG-Export
    if export_options.create_png and 'svg' in output_files:
        png_file = f"{base_name}_vectors.png"
        success = export_to_png(
            output_files['svg'], 
            png_file, 
            config, 
            analysis_result.page_info.width,
            analysis_result.page_info.height
        )
        if success:
            output_files['png'] = png_file
    
    return output_files


def create_analysis_result_from_legacy_data(drawings: List[Dict[str, Any]], 
                                          page_rect,
                                          page_number: int, 
                                          continuous_groups: List[List[Dict]], 
                                          broken_connections: List[Dict], 
                                          circles: List[Dict],
                                          config: AnalysisConfig) -> VectorAnalysisResult:
    """Erstellt strukturierte Analyseergebnisse aus Legacy-Daten.
    
    Diese Funktion konvertiert die ursprünglichen Datenstrukturen 
    in die neuen Pydantic-Modelle für Kompatibilität.
    
    Args:
        drawings: Rohe Zeichenelemente
        page_rect: Seitenrechteck
        page_number: Seitennummer  
        continuous_groups: Bereits analysierte Gruppen
        broken_connections: Unterbrochene Verbindungen
        circles: Erkannte Kreise
        config: Analyse-Konfiguration
        
    Returns:
        VectorAnalysisResult-Objekt
    """
    # Seiteninformationen
    page_info = PageInfo(
        page_number=page_number,
        width=float(page_rect.width),
        height=float(page_rect.height),
        total_drawings=len(drawings)
    )
    
    # Konvertiere Kreise zu Pydantic-Modellen
    pydantic_circles = []
    for circle_dict in circles:
        pydantic_circles.append(Circle(
            index=circle_dict['index'],
            center=_ensure_point(circle_dict['center']),
            radius=circle_dict['radius'],
            coefficient_of_variation=circle_dict['coefficient_of_variation'],
            segments=circle_dict['segments'],
            is_closed=circle_dict['is_closed'],
            is_filled=circle_dict['is_filled'],
            drawing_data=None  # Entferne PyMuPDF-Objekte für JSON-Serialisierung
        ))
    
    # Konvertiere broken_connections zu Pydantic-Modellen
    pydantic_broken_connections = []
    for conn in broken_connections:
        pydantic_broken_connections.append(BrokenConnection(
            path1_index=conn['path1_index'],
            path2_index=conn['path2_index'],
            gap_start=_ensure_point(conn['gap_start']),
            gap_end=_ensure_point(conn['gap_end']),
            gap_length=float(conn['gap_length'])
        ))
    
    # Analysiere Gruppen und kategorisiere sie
    structural_groups, text_like_groups, single_elements = categorize_groups(
        continuous_groups, pydantic_circles, config
    )
    
    # Sammle alle Pfadelemente
    all_paths = []
    for group in continuous_groups:
        for item in group:
            if item['type'] == 'path':
                path_elem = PathElement(
                    index=item['index'],
                    type=item['type'],
                    path_data=item['path_data'],
                    start_point=_ensure_point(item['start']),
                    end_point=_ensure_point(item['end'])
                )
                all_paths.append(path_elem)
    
    # Statistiken erstellen
    statistics = _calculate_statistics(
        drawings, pydantic_circles, all_paths, pydantic_circles, [],  # Alle als definitive behandeln
        structural_groups, text_like_groups, single_elements, 
        pydantic_broken_connections, continuous_groups
    )
    
    return VectorAnalysisResult(
        page_info=page_info,
        all_circles=pydantic_circles,
        all_paths=all_paths,
        structural_groups=structural_groups,
        text_like_groups=text_like_groups,
        single_elements=single_elements,
        broken_connections=pydantic_broken_connections,
        statistics=statistics,
        config=config,
        analysis_timestamp=datetime.now().isoformat()
    )


def _ensure_point(point_like) -> Point:
    """Stellt sicher, dass ein punkt-ähnliches Objekt ein Point ist."""
    if isinstance(point_like, Point):
        return point_like
    elif hasattr(point_like, 'x') and hasattr(point_like, 'y'):
        return Point(x=float(point_like.x), y=float(point_like.y))
    elif isinstance(point_like, (list, tuple)) and len(point_like) >= 2:
        return Point(x=float(point_like[0]), y=float(point_like[1]))
    else:
        # Fallback
        return Point(x=0.0, y=0.0)


def _calculate_statistics(drawings: List[Dict[str, Any]], 
                         all_circles: List[Circle],
                         all_paths: List[PathElement],
                         definitive_circles: List[Circle],
                         potential_circles: List[Circle],
                         structural_groups: List[StructuralGroup],
                         text_like_groups: List[StructuralGroup],
                         single_elements: List[PathElement],
                         broken_connections: List[BrokenConnection],
                         continuous_groups: List[List[Dict]]) -> AnalysisStatistics:
    """Berechnet detaillierte Statistiken der Analyse."""
    
    # Basis-Statistiken
    stats = AnalysisStatistics(
        total_elements=len(drawings),
        total_circles=len(all_circles),
        total_paths=len(all_paths),
        structural_groups=len(structural_groups),
        text_like_groups=len(text_like_groups),
        single_elements=len(single_elements),
        broken_connections=len(broken_connections),
        total_groups=len(continuous_groups),
        definitive_circles=len(definitive_circles),
        potential_circles=len(potential_circles)
    )
    
    # Erweiterte Statistiken
    if continuous_groups:
        group_sizes = [len(group) for group in continuous_groups]
        stats.average_group_size = sum(group_sizes) / len(group_sizes)
        stats.largest_group_size = max(group_sizes)
    
    # Gesamtlänge aller Pfade
    total_length = 0.0
    for path in all_paths:
        total_length += path.calculate_length()
    stats.total_path_length = total_length
    
    # Abdeckungsrate (erkannte vs. gesamte Elemente)
    recognized_elements = (len(structural_groups) + len(text_like_groups) + len(single_elements))
    if len(drawings) > 0:
        stats.coverage_ratio = recognized_elements / len(drawings)
    
    stats.calculate_averages()
    
    return stats


def analyze_special_shapes(drawings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Analysiert verschiedene spezielle Formen in den Zeichnungen.
    
    Legacy-Kompatibilitätsfunktion.
    """
    rectangles = 0
    curves = 0
    lines = 0
    complex_shapes = 0
    
    for drawing in drawings:
        items = drawing.get("items", [])
        
        # Zähle verschiedene Elementtypen
        has_rect = any(item[0] == "re" for item in items)
        has_curves = any(item[0] in ["c", "v", "y"] for item in items)
        has_lines = any(item[0] == "l" for item in items)
        
        if has_rect:
            rectangles += 1
        elif has_curves:
            curves += 1
        elif has_lines:
            if len(items) > 5:
                complex_shapes += 1
            else:
                lines += 1
    
    return {
        'rectangles': rectangles,
        'curves': curves, 
        'lines': lines,
        'complex_shapes': complex_shapes
    }