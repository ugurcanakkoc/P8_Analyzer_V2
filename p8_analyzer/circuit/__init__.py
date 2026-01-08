"""
P8 Analyzer Circuit - Connection Analysis

Provides circuit connection analysis and netlist generation.
"""

from .connection_logic import (
    CircuitComponent,
    UnionFind,
    merge_connected_groups,
    check_intersections,
    check_intersections_legacy,
)

__all__ = [
    "CircuitComponent",
    "UnionFind",
    "merge_connected_groups",
    "check_intersections",
    "check_intersections_legacy",
]
