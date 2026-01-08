"""
P8 Analyzer - PDF Electrical Schematic Analysis Tool

Analyzes P8-format PDF electrical drawings to detect terminals,
read labels, and generate connection reports (netlists).
"""

__version__ = "2.0.0"
__author__ = "neurawork GmbH"

# Core analysis
from p8_analyzer.core import (
    analyze_page_vectors,
    DEFAULT_CONFIG,
    VectorAnalysisResult,
    StructuralGroup,
    Point,
    Circle,
    PathElement,
)

# Detection modules
from p8_analyzer.detection import (
    TerminalDetector,
    TerminalReader,
    TerminalGrouper,
    PinFinder,
)

# Text extraction
from p8_analyzer.text import HybridTextEngine

# Circuit analysis
from p8_analyzer.circuit import check_intersections, CircuitComponent

__all__ = [
    # Version
    "__version__",
    # Core
    "analyze_page_vectors",
    "DEFAULT_CONFIG",
    "VectorAnalysisResult",
    "StructuralGroup",
    "Point",
    "Circle",
    "PathElement",
    # Detection
    "TerminalDetector",
    "TerminalReader",
    "TerminalGrouper",
    "PinFinder",
    # Text
    "HybridTextEngine",
    # Circuit
    "check_intersections",
    "CircuitComponent",
]
