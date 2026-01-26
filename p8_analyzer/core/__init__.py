"""
P8 Analyzer Core - Vector Analysis Engine

Provides PDF vector extraction and structural analysis for electrical schematics.
"""

from .models import (
    Point,
    Circle,
    PathElement,
    AnalysisConfig,
    BrokenConnection,
    WireJunction,
    DetectedElement,
    StructuralGroup,
    PageInfo,
    AnalysisStatistics,
    VectorAnalysisResult,
    ExportOptions,
    DEFAULT_CONFIG,
)

from .geometry import (
    distance_between_points,
    calculate_vector_angle,
    extend_line,
    is_perpendicular_connection,
)

from .circle_analysis import analyze_circles_in_drawings

from .path_analysis import (
    trace_continuous_lines_with_circles,
    find_broken_line_connections,
    categorize_groups,
    find_wire_junctions,
    create_detected_elements,
)

from .svg_export import create_svg_from_analysis_result, export_to_png

from .analyzer import analyze_page_vectors, export_analysis_results

from .analysis_engine import AnalysisEngine, AnalysisOptions as EngineOptions

from .session import (
    WireAnnotationType,
    WireAnnotation,
    Terminal,
    Pin,
    Component,
    Connection,
    PageAnalysis,
    SessionMetadata,
    AnalysisSummary,
    AnalysisSession,
    create_session,
    classify_annotation,
    DIN_COLOR_CODES,
    ANNOTATION_PATTERNS,
)

__all__ = [
    # Models
    "Point",
    "Circle",
    "PathElement",
    "AnalysisConfig",
    "BrokenConnection",
    "WireJunction",
    "DetectedElement",
    "StructuralGroup",
    "PageInfo",
    "AnalysisStatistics",
    "VectorAnalysisResult",
    "ExportOptions",
    "DEFAULT_CONFIG",
    # Geometry
    "distance_between_points",
    "calculate_vector_angle",
    "extend_line",
    "is_perpendicular_connection",
    # Analysis
    "analyze_circles_in_drawings",
    "trace_continuous_lines_with_circles",
    "find_broken_line_connections",
    "categorize_groups",
    "find_wire_junctions",
    "create_detected_elements",
    # Export
    "create_svg_from_analysis_result",
    "export_to_png",
    # Main
    "analyze_page_vectors",
    "export_analysis_results",
    # Analysis Engine
    "AnalysisEngine",
    "EngineOptions",
    # Session models
    "WireAnnotationType",
    "WireAnnotation",
    "Terminal",
    "Pin",
    "Component",
    "Connection",
    "PageAnalysis",
    "SessionMetadata",
    "AnalysisSummary",
    "AnalysisSession",
    "create_session",
    "classify_annotation",
    "DIN_COLOR_CODES",
    "ANNOTATION_PATTERNS",
]
