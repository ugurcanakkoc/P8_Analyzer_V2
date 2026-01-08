"""
Circuit Logic Module - Connection detection between components and wires.

This module handles the detection of electrical connections between
circuit components (boxes) and wire paths (structural groups).

Key feature: Network merging for forked/branching paths.
When wires fork, they may be split into multiple structural groups.
This module merges groups that share common endpoints into logical networks.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Tuple, Optional
import logging

# Import from p8_analyzer core
from p8_analyzer.core import VectorAnalysisResult, Point


logger = logging.getLogger(__name__)


@dataclass
class CircuitComponent:
    """
    Represents a circuit component box.
    Defined here to avoid polluting src/models.py.
    """
    id: str
    label: str
    bbox: Dict[str, float]  # {min_x, min_y, max_x, max_y}

    def contains_point(self, point: Point, tolerance: float = 0.0) -> bool:
        """Check if a point is inside this component's bounding box."""
        return (self.bbox["min_x"] - tolerance <= point.x <= self.bbox["max_x"] + tolerance and
                self.bbox["min_y"] - tolerance <= point.y <= self.bbox["max_y"] + tolerance)


class UnionFind:
    """
    Union-Find (Disjoint Set Union) data structure for efficient network merging.

    Used to group structural groups that share common connection points,
    enabling proper handling of forked/branching wire paths.
    """

    def __init__(self, n: int):
        """Initialize with n elements (0 to n-1)."""
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """Find the root of element x with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """
        Merge the sets containing x and y.
        Returns True if merge happened, False if already in same set.
        """
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x == root_y:
            return False

        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1

        return True

    def get_groups(self) -> Dict[int, List[int]]:
        """Get all groups as a dict of root -> list of members."""
        groups: Dict[int, List[int]] = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(i)
        return groups


def _points_are_close(p1: Point, p2: Point, tolerance: float = 2.0) -> bool:
    """Check if two points are within tolerance distance."""
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return (dx * dx + dy * dy) <= (tolerance * tolerance)


def _get_group_endpoints(group) -> List[Point]:
    """
    Extract all endpoint coordinates from a structural group.
    Includes line start/end points and circle centers.
    """
    points = []

    # Line segment endpoints
    for elem in group.elements:
        points.append(elem.start_point)
        points.append(elem.end_point)

    # Circle centers (terminals/connection points)
    for circle in group.circles:
        points.append(circle.center)

    return points


def merge_connected_groups(
    structural_groups: List[Any],
    point_tolerance: float = 2.0
) -> Dict[int, List[int]]:
    """
    Merge structural groups that share common endpoints into logical networks.

    This handles forked/branching paths where a single logical wire network
    is split into multiple structural groups by the vector analysis.

    Args:
        structural_groups: List of StructuralGroup objects from UVP analysis
        point_tolerance: Maximum distance between points to consider them connected

    Returns:
        Dictionary mapping network root index to list of group indices in that network
    """
    if not structural_groups:
        return {}

    n = len(structural_groups)
    uf = UnionFind(n)

    # Collect all endpoints for each group
    group_points: List[List[Point]] = []
    for group in structural_groups:
        group_points.append(_get_group_endpoints(group))

    # Find groups that share common endpoints
    # O(n^2) comparison, but n is typically small (<100 groups per page)
    for i in range(n):
        for j in range(i + 1, n):
            # Check if any point in group i is close to any point in group j
            for p1 in group_points[i]:
                for p2 in group_points[j]:
                    if _points_are_close(p1, p2, point_tolerance):
                        uf.union(i, j)
                        # Once connected, no need to check more points
                        break
                else:
                    continue
                break

    merged_groups = uf.get_groups()

    # Log merging info for debugging
    merge_count = sum(1 for members in merged_groups.values() if len(members) > 1)
    if merge_count > 0:
        logger.debug(f"Merged {merge_count} network groups (forked paths detected)")

    return merged_groups


def check_intersections(
    components: List[CircuitComponent],
    analysis_result: VectorAnalysisResult,
    merge_networks: bool = True,
    point_tolerance: float = 2.0,
    box_tolerance: float = 5.0
) -> Dict[str, List[str]]:
    """
    Find connections between circuit components and wire paths.

    Handles forked/branching paths by merging structural groups that share
    common endpoints into single logical networks before checking connections.

    Args:
        components: List of CircuitComponent boxes to check
        analysis_result: Vector analysis result containing structural groups
        merge_networks: If True, merge groups sharing endpoints (fixes forked paths)
        point_tolerance: Distance tolerance for considering points as connected
        box_tolerance: Distance tolerance for point-in-box checks

    Returns:
        Dictionary mapping network IDs to lists of connected component IDs
        Example: {'NET-001': ['BOX-1', 'BOX-2', 'Terminal-X1:1']}
    """
    connections_map: Dict[str, List[str]] = {}

    if not analysis_result or not analysis_result.structural_groups:
        return connections_map

    structural_groups = analysis_result.structural_groups

    if merge_networks:
        # Merge groups that share common endpoints (handles forked paths)
        merged_networks = merge_connected_groups(structural_groups, point_tolerance)
    else:
        # Treat each group as a separate network (old behavior)
        merged_networks = {i: [i] for i in range(len(structural_groups))}

    # Process each merged network
    network_index = 0
    for root_idx, group_indices in sorted(merged_networks.items()):
        network_index += 1
        net_name = f"NET-{network_index:03d}"

        connected_boxes: List[str] = []
        seen_boxes: Set[str] = set()  # Avoid duplicates

        # Collect all points from all groups in this network
        points_to_check: List[Point] = []
        for group_idx in group_indices:
            group = structural_groups[group_idx]
            points_to_check.extend(_get_group_endpoints(group))

        # Check each component for intersection with network points
        for comp in components:
            if comp.id in seen_boxes:
                continue

            for point in points_to_check:
                if comp.contains_point(point, tolerance=box_tolerance):
                    connected_boxes.append(comp.id)
                    seen_boxes.add(comp.id)
                    break

        # Only record networks that connect to at least one component
        if connected_boxes:
            connections_map[net_name] = connected_boxes

    return connections_map


def check_intersections_legacy(
    components: List[CircuitComponent],
    analysis_result: VectorAnalysisResult
) -> Dict[str, List[str]]:
    """
    Legacy version without network merging.
    Kept for backwards compatibility and comparison testing.
    """
    return check_intersections(
        components,
        analysis_result,
        merge_networks=False
    )
