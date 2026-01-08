"""
P8 Component Detector - Label + Line Break Merging.

Detects electrical components by merging:
1. Component labels (found via regex: -X1, -1G35, etc.)
2. FILTERED wire breaks from structural groups (same filter as UVP gap fills)
3. Circle pins from structural groups

Key constraints:
- Only use breaks where path1_index belongs to a structural group
- Vertical distance is weighted more heavily than horizontal
- Component bounding boxes must NEVER overlap
- Components inherit color from their circuit group
"""

import math
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
import pymupdf
from PIL import Image, ImageDraw

from .label_detector import LabelDetector, DetectedLabel
from ..core.models import (
    DetectedElement, StructuralGroup, Point, Circle, BrokenConnection, PathElement
)


@dataclass
class FilteredGapFill:
    """A gap fill that belongs to a structural group (same filter as UVP svg_export)."""
    gap_start: Tuple[float, float]
    gap_end: Tuple[float, float]
    color: str
    path1_index: int
    path2_index: int
    gap_length: float

    @property
    def center(self) -> Tuple[float, float]:
        """Get center point of the gap."""
        return (
            (self.gap_start[0] + self.gap_end[0]) / 2,
            (self.gap_start[1] + self.gap_end[1]) / 2
        )

    def get_bounding_box(self, padding: float = 5.0) -> Dict[str, float]:
        """Calculate bounding box around the gap."""
        min_x = min(self.gap_start[0], self.gap_end[0]) - padding
        max_x = max(self.gap_start[0], self.gap_end[0]) + padding
        min_y = min(self.gap_start[1], self.gap_end[1]) - padding
        max_y = max(self.gap_start[1], self.gap_end[1]) + padding
        return {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y}


@dataclass
class FilteredCirclePin:
    """A circle pin that belongs to a structural group."""
    center: Tuple[float, float]
    radius: float
    color: str
    group_id: int
    is_filled: bool = False

    def get_bounding_box(self, padding: float = 2.0) -> Dict[str, float]:
        """Calculate bounding box around the circle."""
        return {
            "min_x": self.center[0] - self.radius - padding,
            "max_x": self.center[0] + self.radius + padding,
            "min_y": self.center[1] - self.radius - padding,
            "max_y": self.center[1] + self.radius + padding
        }


@dataclass
class FilteredLineEnd:
    """A terminal line endpoint that could connect to a component.

    These are endpoints of lines that don't connect to other lines
    (i.e., they're "free" ends that likely connect to components).
    """
    position: Tuple[float, float]
    color: str
    group_id: int
    path_index: int
    is_start: bool  # True if this is start_point, False if end_point

    def get_bounding_box(self, padding: float = 3.0) -> Dict[str, float]:
        """Calculate bounding box around the endpoint."""
        return {
            "min_x": self.position[0] - padding,
            "max_x": self.position[0] + padding,
            "min_y": self.position[1] - padding,
            "max_y": self.position[1] + padding
        }


@dataclass
class DetectedComponent:
    """A detected electrical component with its location and properties."""
    component_id: int
    label: DetectedLabel
    gap_fills: List[FilteredGapFill] = field(default_factory=list)
    circle_pins: List[FilteredCirclePin] = field(default_factory=list)
    line_ends: List[FilteredLineEnd] = field(default_factory=list)
    bounding_box: Tuple[float, float, float, float] = None  # (x0, y0, x1, y1)
    confidence: float = 0.0
    color: str = "#00AA00"  # Default green, will be set from circuit group

    @property
    def center(self) -> Tuple[float, float]:
        """Get center point of component."""
        if self.bounding_box:
            return (
                (self.bounding_box[0] + self.bounding_box[2]) / 2,
                (self.bounding_box[1] + self.bounding_box[3]) / 2
            )
        return self.label.center

    @property
    def name(self) -> str:
        """Get component name from label."""
        return self.label.text

    @property
    def element_count(self) -> int:
        """Total number of elements (gap fills + pins + line ends) associated with this component."""
        return len(self.gap_fills) + len(self.circle_pins) + len(self.line_ends)

    # Keep wire_breaks as alias for backward compatibility
    @property
    def wire_breaks(self) -> List[FilteredGapFill]:
        return self.gap_fills


class ComponentDetector:
    """
    Detects components by merging labels with deduplicated wire breaks.

    Uses anisotropic distance weighting where vertical distance
    is penalized more than horizontal distance.

    Features:
    - Dotted line detection: lines with >10% gap ratio are considered dotted
      and their breaks are excluded from component detection
    """

    def __init__(self,
                 max_horizontal_distance: float = 100.0,
                 max_vertical_distance: float = 40.0,
                 vertical_weight: float = 3.0,
                 min_component_size: float = 20.0,
                 padding: float = 5.0,
                 dotted_line_threshold: float = 0.10):
        """
        Initialize component detector.

        Args:
            max_horizontal_distance: Max horizontal distance from break to label
            max_vertical_distance: Max vertical distance from break to label
            vertical_weight: How much more to penalize vertical distance
            min_component_size: Minimum component bounding box size
            padding: Padding around component bounding box
            dotted_line_threshold: Gap ratio threshold for dotted line detection (default 10%)
        """
        self.max_horizontal_distance = max_horizontal_distance
        self.max_vertical_distance = max_vertical_distance
        self.vertical_weight = vertical_weight
        self.min_component_size = min_component_size
        self.padding = padding
        self.dotted_line_threshold = dotted_line_threshold
        self.label_detector = LabelDetector()

    def _weighted_distance(self,
                          label_center: Tuple[float, float],
                          break_center: Tuple[float, float]) -> float:
        """
        Calculate anisotropic distance with vertical weighting.

        Vertical distance is penalized more than horizontal because
        components tend to be laid out horizontally along wire runs.
        """
        dx = abs(label_center[0] - break_center[0])
        dy = abs(label_center[1] - break_center[1])

        # Apply vertical weight
        weighted_dy = dy * self.vertical_weight

        return math.sqrt(dx**2 + weighted_dy**2)

    def _is_break_in_range(self,
                          label_center: Tuple[float, float],
                          break_center: Tuple[float, float]) -> bool:
        """Check if break is within acceptable range of label."""
        dx = abs(label_center[0] - break_center[0])
        dy = abs(label_center[1] - break_center[1])

        return (dx <= self.max_horizontal_distance and
                dy <= self.max_vertical_distance)

    def _boxes_overlap(self,
                       box1: Tuple[float, float, float, float],
                       box2: Tuple[float, float, float, float]) -> bool:
        """Check if two bounding boxes overlap."""
        x0_1, y0_1, x1_1, y1_1 = box1
        x0_2, y0_2, x1_2, y1_2 = box2

        # No overlap if one box is completely to the left/right/above/below
        if x1_1 < x0_2 or x1_2 < x0_1:
            return False
        if y1_1 < y0_2 or y1_2 < y0_1:
            return False
        return True

    def _shrink_to_avoid_overlap(self,
                                 new_box: Tuple[float, float, float, float],
                                 existing_boxes: List[Tuple[float, float, float, float]],
                                 label_bbox: Tuple[float, float, float, float]
                                 ) -> Tuple[float, float, float, float]:
        """
        Shrink a box to avoid overlapping with existing boxes.
        Always keeps the label bbox intact.
        """
        x0, y0, x1, y1 = new_box
        lx0, ly0, lx1, ly1 = label_bbox

        for ex_box in existing_boxes:
            if not self._boxes_overlap((x0, y0, x1, y1), ex_box):
                continue

            ex0, ey0, ex1, ey1 = ex_box

            # Try to shrink from each side, keeping label visible
            # Shrink from left
            if x0 < ex1 and x1 > ex1:
                new_x0 = max(x0, ex1 + 1)
                if new_x0 <= lx0:  # Label still visible
                    x0 = new_x0
                    continue

            # Shrink from right
            if x1 > ex0 and x0 < ex0:
                new_x1 = min(x1, ex0 - 1)
                if new_x1 >= lx1:  # Label still visible
                    x1 = new_x1
                    continue

            # Shrink from top
            if y0 < ey1 and y1 > ey1:
                new_y0 = max(y0, ey1 + 1)
                if new_y0 <= ly0:  # Label still visible
                    y0 = new_y0
                    continue

            # Shrink from bottom
            if y1 > ey0 and y0 < ey0:
                new_y1 = min(y1, ey0 - 1)
                if new_y1 >= ly1:  # Label still visible
                    y1 = new_y1
                    continue

        return (x0, y0, x1, y1)

    def _create_bounding_box(self,
                             label: DetectedLabel,
                             gap_fills: List[FilteredGapFill],
                             circles: List[FilteredCirclePin] = None,
                             line_ends: List[FilteredLineEnd] = None) -> Tuple[float, float, float, float]:
        """Create minimal bounding box covering label, gap fills, circles, and line ends."""
        # Start with label bbox
        x0, y0, x1, y1 = label.bbox

        # Expand to include all gap fills
        for gap in gap_fills:
            bbox = gap.get_bounding_box()
            x0 = min(x0, bbox["min_x"])
            y0 = min(y0, bbox["min_y"])
            x1 = max(x1, bbox["max_x"])
            y1 = max(y1, bbox["max_y"])

        # Expand to include all circles
        if circles:
            for circ in circles:
                bbox = circ.get_bounding_box()
                x0 = min(x0, bbox["min_x"])
                y0 = min(y0, bbox["min_y"])
                x1 = max(x1, bbox["max_x"])
                y1 = max(y1, bbox["max_y"])

        # Expand to include all line ends
        if line_ends:
            for end in line_ends:
                bbox = end.get_bounding_box()
                x0 = min(x0, bbox["min_x"])
                y0 = min(y0, bbox["min_y"])
                x1 = max(x1, bbox["max_x"])
                y1 = max(y1, bbox["max_y"])

        # Ensure minimum size
        width = x1 - x0
        height = y1 - y0

        if width < self.min_component_size:
            expand = (self.min_component_size - width) / 2
            x0 -= expand
            x1 += expand

        if height < self.min_component_size:
            expand = (self.min_component_size - height) / 2
            y0 -= expand
            y1 += expand

        # Add padding
        return (x0 - self.padding, y0 - self.padding,
                x1 + self.padding, y1 + self.padding)

    def _identify_dotted_line_breaks(self,
                                      broken_connections: List[BrokenConnection],
                                      structural_groups: List[StructuralGroup]
                                      ) -> Tuple[Set[Tuple[int, int]], Dict[int, float]]:
        """
        Identify breaks that are part of dotted lines.

        A dotted line is defined as a structural group where the ratio of
        total gap length to total path length exceeds the threshold (default 10%).

        Args:
            broken_connections: All broken connections
            structural_groups: All structural groups

        Returns:
            Tuple of:
            - Set of (path1_index, path2_index) pairs to exclude
            - Dict mapping group_id to gap_ratio for debugging
        """
        dotted_breaks: Set[Tuple[int, int]] = set()
        group_gap_ratios: Dict[int, float] = {}

        for group in structural_groups:
            # Get all element indices in this group
            group_element_indices = {elem.index for elem in group.elements}

            # Calculate total path length in this group
            total_path_length = 0.0
            for elem in group.elements:
                total_path_length += elem.calculate_length()

            if total_path_length == 0:
                continue

            # Find all breaks that belong to this group
            # A break belongs to a group if path1_index is in the group
            group_breaks = []
            total_gap_length = 0.0
            for conn in broken_connections:
                if conn.path1_index in group_element_indices:
                    group_breaks.append(conn)
                    total_gap_length += conn.gap_length

            # Calculate gap ratio
            # Include gap length in total for proper ratio calculation
            total_length = total_path_length + total_gap_length
            gap_ratio = total_gap_length / total_length if total_length > 0 else 0

            group_gap_ratios[group.group_id] = gap_ratio

            # If gap ratio exceeds threshold, mark all breaks in this group as dotted
            if gap_ratio > self.dotted_line_threshold:
                for conn in group_breaks:
                    dotted_breaks.add((conn.path1_index, conn.path2_index))

        return dotted_breaks, group_gap_ratios

    def _filter_gap_fills(self,
                          broken_connections: List[BrokenConnection],
                          structural_groups: List[StructuralGroup]
                          ) -> Tuple[List[FilteredGapFill], int, int]:
        """
        Filter broken_connections to only those belonging to structural groups,
        excluding dotted line breaks.

        This is the same filtering logic used by UVP svg_export._draw_gap_fills(),
        with additional filtering for dotted lines.

        Returns:
            Tuple of (filtered_gap_fills, dotted_count, groups_with_dotted)
        """
        # First, identify dotted line breaks
        dotted_breaks, group_gap_ratios = self._identify_dotted_line_breaks(
            broken_connections, structural_groups
        )

        # Count groups with dotted lines
        dotted_groups = [gid for gid, ratio in group_gap_ratios.items()
                        if ratio > self.dotted_line_threshold]

        if dotted_breaks:
            print(f"  Dotted line detection: {len(dotted_breaks)} breaks excluded "
                  f"({len(dotted_groups)} groups with >{self.dotted_line_threshold*100:.0f}% gap ratio)")
            # Show top dotted groups for debugging
            sorted_ratios = sorted(group_gap_ratios.items(), key=lambda x: x[1], reverse=True)
            for gid, ratio in sorted_ratios[:3]:
                if ratio > self.dotted_line_threshold:
                    print(f"    Group {gid}: {ratio*100:.1f}% gap ratio")

        # Build mapping from element index to group color
        element_to_color: Dict[int, str] = {}
        for group in structural_groups:
            for elem in group.elements:
                element_to_color[elem.index] = group.color

        # Filter and convert to FilteredGapFill, excluding dotted line breaks
        filtered = []
        dotted_count = 0
        for conn in broken_connections:
            # Skip dotted line breaks
            if (conn.path1_index, conn.path2_index) in dotted_breaks:
                dotted_count += 1
                continue

            color = element_to_color.get(conn.path1_index)
            if color:  # Only include if path1_index belongs to a structural group
                filtered.append(FilteredGapFill(
                    gap_start=(conn.gap_start.x, conn.gap_start.y),
                    gap_end=(conn.gap_end.x, conn.gap_end.y),
                    color=color,
                    path1_index=conn.path1_index,
                    path2_index=conn.path2_index,
                    gap_length=conn.gap_length
                ))

        return filtered, dotted_count, len(dotted_groups)

    def _filter_circle_pins(self,
                           structural_groups: List[StructuralGroup]
                           ) -> List[FilteredCirclePin]:
        """
        Extract circle pins from structural groups.

        Each structural group may contain circles - these are the valid circuit pins.
        """
        filtered = []
        for group in structural_groups:
            for circle in group.circles:
                filtered.append(FilteredCirclePin(
                    center=(circle.center.x, circle.center.y),
                    radius=circle.radius,
                    color=group.color,
                    group_id=group.group_id,
                    is_filled=circle.is_filled
                ))
        return filtered

    def _filter_line_ends(self,
                          structural_groups: List[StructuralGroup],
                          broken_connections: List[BrokenConnection],
                          connection_tolerance: float = 3.0
                          ) -> List[FilteredLineEnd]:
        """
        Extract terminal line endpoints from structural groups.

        Terminal endpoints are line ends that don't connect to other lines,
        i.e., they're "free" ends that likely connect to components.

        Args:
            structural_groups: All structural groups
            broken_connections: All broken connections (to exclude break endpoints)
            connection_tolerance: Distance tolerance for considering endpoints connected

        Returns:
            List of FilteredLineEnd for endpoints that don't connect to other lines
        """
        # Collect all endpoints with their context
        all_endpoints: List[Tuple[Tuple[float, float], int, int, bool, str]] = []  # (pos, path_idx, group_id, is_start, color)

        for group in structural_groups:
            for elem in group.elements:
                if elem.start_point:
                    all_endpoints.append((
                        (elem.start_point.x, elem.start_point.y),
                        elem.index,
                        group.group_id,
                        True,
                        group.color
                    ))
                if elem.end_point:
                    all_endpoints.append((
                        (elem.end_point.x, elem.end_point.y),
                        elem.index,
                        group.group_id,
                        False,
                        group.color
                    ))

        # Collect positions that are "used" by broken connections
        # These are the gap_start and gap_end points
        used_positions: Set[Tuple[float, float]] = set()
        for conn in broken_connections:
            used_positions.add((conn.gap_start.x, conn.gap_start.y))
            used_positions.add((conn.gap_end.x, conn.gap_end.y))

        # Collect circle centers (endpoints near circles are connected)
        circle_centers: List[Tuple[float, float]] = []
        for group in structural_groups:
            for circle in group.circles:
                circle_centers.append((circle.center.x, circle.center.y))

        def is_near_position(pos1: Tuple[float, float], pos2: Tuple[float, float], tol: float) -> bool:
            dx = pos1[0] - pos2[0]
            dy = pos1[1] - pos2[1]
            return (dx*dx + dy*dy) <= tol*tol

        def is_endpoint_used(pos: Tuple[float, float]) -> bool:
            # Check if near a break position
            for used_pos in used_positions:
                if is_near_position(pos, used_pos, connection_tolerance):
                    return True
            # Check if near a circle
            for circle_pos in circle_centers:
                if is_near_position(pos, circle_pos, connection_tolerance * 2):
                    return True
            return False

        # Check if endpoints connect to other endpoints (same position = connected)
        endpoint_counts: Dict[Tuple[int, int], int] = {}  # Rounded position -> count
        round_factor = 1.0  # Round to 1 PDF unit

        for pos, path_idx, group_id, is_start, color in all_endpoints:
            rounded = (round(pos[0] / round_factor), round(pos[1] / round_factor))
            endpoint_counts[rounded] = endpoint_counts.get(rounded, 0) + 1

        # Filter to only terminal (free) endpoints
        filtered = []
        for pos, path_idx, group_id, is_start, color in all_endpoints:
            # Skip if this endpoint is used by a broken connection or circle
            if is_endpoint_used(pos):
                continue

            # Skip if multiple endpoints at same position (means lines connect there)
            rounded = (round(pos[0] / round_factor), round(pos[1] / round_factor))
            if endpoint_counts.get(rounded, 0) > 1:
                continue

            filtered.append(FilteredLineEnd(
                position=pos,
                color=color,
                group_id=group_id,
                path_index=path_idx,
                is_start=is_start
            ))

        return filtered

    def detect_components(self,
                         page: pymupdf.Page,
                         broken_connections: List[BrokenConnection],
                         structural_groups: List[StructuralGroup]
                         ) -> Tuple[List[DetectedComponent], List[DetectedLabel], List[FilteredGapFill], List[FilteredCirclePin], List[FilteredLineEnd]]:
        """
        Detect components by merging labels with FILTERED gap fills, circle pins, and line ends.

        Uses the same filtering logic as UVP svg_export:
        - Only broken_connections where path1_index belongs to a structural group
        - Only circles that belong to structural groups
        - Terminal line endpoints (free ends not connected to other lines)

        Args:
            page: PyMuPDF page object
            broken_connections: List of BrokenConnection from analysis
            structural_groups: List of StructuralGroup from analysis

        Returns:
            Tuple of (components, labels, filtered_gap_fills, filtered_circle_pins, filtered_line_ends)
        """
        # Step 1: Detect labels
        labels = self.label_detector.detect_labels(page)
        print(f"Step 1: Found {len(labels)} labels")

        # Step 2: Filter gap fills (same logic as UVP svg_export + dotted line exclusion)
        gap_fills, dotted_count, dotted_groups = self._filter_gap_fills(broken_connections, structural_groups)
        in_structural = len(gap_fills) + dotted_count
        print(f"Step 2: Filtered {len(gap_fills)}/{len(broken_connections)} gap fills "
              f"({in_structural} in structural groups, {dotted_count} excluded as dotted lines)")

        # Step 3: Filter circle pins (only from structural groups)
        circle_pins = self._filter_circle_pins(structural_groups)
        print(f"Step 3: Found {len(circle_pins)} circle pins in structural groups")

        # Step 4: Filter line ends (terminal endpoints not connected to other lines)
        line_ends = self._filter_line_ends(structural_groups, broken_connections)
        print(f"Step 4: Found {len(line_ends)} terminal line endpoints")

        # Step 5: Assign gap fills, circles, and line ends to labels
        label_gaps: Dict[int, List[FilteredGapFill]] = {i: [] for i in range(len(labels))}
        label_circles: Dict[int, List[FilteredCirclePin]] = {i: [] for i in range(len(labels))}
        label_line_ends: Dict[int, List[FilteredLineEnd]] = {i: [] for i in range(len(labels))}
        used_gaps: Set[int] = set()
        used_circles: Set[int] = set()
        used_line_ends: Set[int] = set()

        # Build distance list for greedy assignment
        distances = []

        # Gap fills to labels
        for gi, gap in enumerate(gap_fills):
            gap_center = gap.center
            for li, label in enumerate(labels):
                if self._is_break_in_range(label.center, gap_center):
                    dist = self._weighted_distance(label.center, gap_center)
                    distances.append((dist, gi, li, 'gap'))

        # Circle pins to labels
        for ci, circ in enumerate(circle_pins):
            for li, label in enumerate(labels):
                if self._is_break_in_range(label.center, circ.center):
                    dist = self._weighted_distance(label.center, circ.center)
                    distances.append((dist, ci, li, 'circle'))

        # Line ends to labels
        for ei, end in enumerate(line_ends):
            for li, label in enumerate(labels):
                if self._is_break_in_range(label.center, end.position):
                    dist = self._weighted_distance(label.center, end.position)
                    distances.append((dist, ei, li, 'line_end'))

        # Sort by distance (closest first)
        distances.sort(key=lambda x: x[0])

        # Greedy assignment
        for dist, idx, li, elem_type in distances:
            if elem_type == 'gap':
                if idx in used_gaps:
                    continue
                label_gaps[li].append(gap_fills[idx])
                used_gaps.add(idx)
            elif elem_type == 'circle':
                if idx in used_circles:
                    continue
                label_circles[li].append(circle_pins[idx])
                used_circles.add(idx)
            else:  # line_end
                if idx in used_line_ends:
                    continue
                label_line_ends[li].append(line_ends[idx])
                used_line_ends.add(idx)

        assigned_gaps = sum(1 for gaps in label_gaps.values() if gaps)
        assigned_circles = sum(1 for circs in label_circles.values() if circs)
        assigned_ends = sum(1 for ends in label_line_ends.values() if ends)
        print(f"Step 5: Assigned gaps to {assigned_gaps}/{len(labels)} labels")
        print(f"        Assigned circles to {assigned_circles}/{len(labels)} labels")
        print(f"        Assigned line ends to {assigned_ends}/{len(labels)} labels")

        # Step 6: Create components with bounding boxes
        components = []
        existing_boxes = []

        for i, label in enumerate(labels):
            assigned_gap_fills = label_gaps[i]
            assigned_pins = label_circles[i]
            assigned_line_ends = label_line_ends[i]

            # Calculate confidence based on elements
            total_elements = len(assigned_gap_fills) + len(assigned_pins) + len(assigned_line_ends)
            if total_elements > 0:
                confidence = min(0.95, 0.5 + total_elements * 0.1)
            else:
                confidence = 0.3  # Label without any elements

            # Create initial bounding box
            bbox = self._create_bounding_box(label, assigned_gap_fills, assigned_pins, assigned_line_ends)

            # Shrink to avoid overlaps
            bbox = self._shrink_to_avoid_overlap(bbox, existing_boxes, label.bbox)

            # Determine color from assigned elements
            color = "#00AA00"  # Default green
            if assigned_gap_fills:
                color = assigned_gap_fills[0].color
            elif assigned_pins:
                color = assigned_pins[0].color
            elif assigned_line_ends:
                color = assigned_line_ends[0].color

            component = DetectedComponent(
                component_id=i,
                label=label,
                gap_fills=assigned_gap_fills,
                circle_pins=assigned_pins,
                line_ends=assigned_line_ends,
                bounding_box=bbox,
                confidence=confidence,
                color=color
            )
            components.append(component)
            existing_boxes.append(bbox)

        # Sort by confidence
        components.sort(key=lambda c: c.confidence, reverse=True)

        print(f"Step 6: Created {len(components)} components")
        print(f"  - With elements: {sum(1 for c in components if c.element_count > 0)}")
        print(f"  - Without elements: {sum(1 for c in components if c.element_count == 0)}")

        return components, labels, gap_fills, circle_pins, line_ends


def visualize_component_detection(
    page: pymupdf.Page,
    labels: List[DetectedLabel],
    gap_fills: List[FilteredGapFill],
    components: List[DetectedComponent],
    output_path: str,
    scale: float = 2.0,
    show_all: bool = True,
    structural_groups: List[StructuralGroup] = None,
    circle_pins: List[FilteredCirclePin] = None,
    line_ends: List[FilteredLineEnd] = None
) -> str:
    """
    Create visualization of component detection with full circuit pipeline.

    Renders:
    1. Structural groups (colored circuit paths)
    2. Gap fills (colored rectangles matching circuit color)
    3. Circle pins (colored circles)
    4. Line ends (colored diamonds at terminal endpoints)
    5. Labels (yellow boxes)
    6. Component bounding boxes (colored by circuit)
    """
    # Render page as base
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img, 'RGBA')

    # Layer 1: Draw structural groups (colored paths)
    if structural_groups:
        for group in structural_groups:
            color_hex = group.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

            # Draw paths
            for elem in group.elements:
                if elem.start_point and elem.end_point:
                    start = (elem.start_point.x * scale, elem.start_point.y * scale)
                    end = (elem.end_point.x * scale, elem.end_point.y * scale)
                    draw.line([start, end], fill=(r, g, b, 200), width=2)

    # Layer 2: Draw gap fills (colored rectangles over breaks)
    for gap in gap_fills:
        color_hex = gap.color.lstrip('#')
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

        # Draw colored rectangle for gap fill
        sx, sy = gap.gap_start[0] * scale, gap.gap_start[1] * scale
        ex, ey = gap.gap_end[0] * scale, gap.gap_end[1] * scale

        # Calculate perpendicular offset for rectangle
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            thickness = 6.0  # Gap fill thickness in pixels
            nx, ny = -dy/length * thickness/2, dx/length * thickness/2
            points = [
                (sx + nx, sy + ny),
                (sx - nx, sy - ny),
                (ex - nx, ey - ny),
                (ex + nx, ey + ny)
            ]
            draw.polygon(points, fill=(r, g, b, 180))

    # Layer 3: Draw circle pins
    if circle_pins:
        for circ in circle_pins:
            color_hex = circ.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

            cx, cy = circ.center[0] * scale, circ.center[1] * scale
            radius = circ.radius * scale

            bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
            if circ.is_filled:
                draw.ellipse(bbox, fill=(r, g, b, 100), outline=(r, g, b), width=2)
            else:
                draw.ellipse(bbox, outline=(r, g, b), width=3)

    # Layer 4: Draw line ends (diamond markers at terminal endpoints)
    if line_ends:
        diamond_size = 4.0 * scale
        for end in line_ends:
            color_hex = end.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

            ex, ey = end.position[0] * scale, end.position[1] * scale
            # Draw diamond shape
            diamond_points = [
                (ex, ey - diamond_size),  # Top
                (ex + diamond_size, ey),  # Right
                (ex, ey + diamond_size),  # Bottom
                (ex - diamond_size, ey),  # Left
            ]
            draw.polygon(diamond_points, fill=(r, g, b, 180), outline=(r, g, b))

    # Layer 5: Draw labels (yellow boxes with text)
    for label in labels:
        x0, y0, x1, y1 = [c * scale for c in label.bbox]
        draw.rectangle([x0, y0, x1, y1],
                      fill=(255, 255, 0, 100),
                      outline=(255, 180, 0),
                      width=2)
        draw.text((x0, y0 - 12), label.text, fill=(180, 100, 0))

    # Layer 6: Draw component bounding boxes with circuit colors
    for comp in components:
        if not show_all and not comp.gap_fills and not comp.line_ends:
            continue

        x0, y0, x1, y1 = [c * scale for c in comp.bounding_box]

        # Parse color from hex
        color_hex = comp.color.lstrip('#')
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

        # Adjust alpha based on confidence
        alpha = int(60 * comp.confidence) if comp.confidence > 0.5 else 20

        has_elements = comp.gap_fills or comp.circle_pins or comp.line_ends
        draw.rectangle([x0, y0, x1, y1],
                      fill=(r, g, b, alpha),
                      outline=(r, g, b),
                      width=3 if has_elements else 1)

        # Draw connection lines from label to elements
        label_center = (comp.label.center[0] * scale, comp.label.center[1] * scale)
        for gap in comp.gap_fills:
            gap_center = (gap.center[0] * scale, gap.center[1] * scale)
            draw.line([label_center, gap_center], fill=(r, g, b, 150), width=1)
        for end in comp.line_ends:
            end_pos = (end.position[0] * scale, end.position[1] * scale)
            draw.line([label_center, end_pos], fill=(r, g, b, 100), width=1)

    img.save(output_path)
    print(f"Saved: {output_path}")
    return output_path


def create_step_visualization(
    page: pymupdf.Page,
    labels: List[DetectedLabel],
    gap_fills: List[FilteredGapFill],
    components: List[DetectedComponent],
    output_dir: str,
    scale: float = 2.0,
    structural_groups: List[StructuralGroup] = None,
    circle_pins: List[FilteredCirclePin] = None,
    line_ends: List[FilteredLineEnd] = None
) -> List[str]:
    """Create step-by-step visualization images showing the full pipeline."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Render base
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    base = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    paths = []

    # Step 1: Original page
    p1 = os.path.join(output_dir, "step1_original.png")
    base.save(p1)
    paths.append(p1)

    # Step 2: Structural groups (colored circuits)
    img2 = base.copy()
    draw2 = ImageDraw.Draw(img2, 'RGBA')
    if structural_groups:
        for group in structural_groups:
            color_hex = group.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            for elem in group.elements:
                if elem.start_point and elem.end_point:
                    start = (elem.start_point.x * scale, elem.start_point.y * scale)
                    end = (elem.end_point.x * scale, elem.end_point.y * scale)
                    draw2.line([start, end], fill=(r, g, b, 220), width=2)
    p2 = os.path.join(output_dir, "step2_circuits.png")
    img2.save(p2)
    paths.append(p2)

    # Step 3: Gap fills, circle pins, and line ends
    img3 = img2.copy()
    draw3 = ImageDraw.Draw(img3, 'RGBA')

    # Draw gap fills
    for gap in gap_fills:
        color_hex = gap.color.lstrip('#')
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
        sx, sy = gap.gap_start[0] * scale, gap.gap_start[1] * scale
        ex, ey = gap.gap_end[0] * scale, gap.gap_end[1] * scale
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            thickness = 8.0
            nx, ny = -dy/length * thickness/2, dx/length * thickness/2
            points = [(sx + nx, sy + ny), (sx - nx, sy - ny), (ex - nx, ey - ny), (ex + nx, ey + ny)]
            draw3.polygon(points, fill=(r, g, b, 200))

    # Draw circle pins
    if circle_pins:
        for circ in circle_pins:
            color_hex = circ.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            cx, cy = circ.center[0] * scale, circ.center[1] * scale
            radius = circ.radius * scale
            bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
            draw3.ellipse(bbox, outline=(r, g, b), width=3)

    # Draw line ends (diamond markers)
    if line_ends:
        diamond_size = 4.0 * scale
        for end in line_ends:
            color_hex = end.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            ex, ey = end.position[0] * scale, end.position[1] * scale
            diamond_points = [
                (ex, ey - diamond_size),
                (ex + diamond_size, ey),
                (ex, ey + diamond_size),
                (ex - diamond_size, ey),
            ]
            draw3.polygon(diamond_points, fill=(r, g, b, 180), outline=(r, g, b))

    p3 = os.path.join(output_dir, "step3_gaps_pins_ends.png")
    img3.save(p3)
    paths.append(p3)

    # Step 4: Labels
    img4 = img3.copy()
    draw4 = ImageDraw.Draw(img4, 'RGBA')
    for label in labels:
        x0, y0, x1, y1 = [c * scale for c in label.bbox]
        draw4.rectangle([x0, y0, x1, y1],
                       fill=(255, 255, 0, 150),
                       outline=(255, 150, 0),
                       width=3)
        draw4.text((x0 - 2, y0 - 16), label.text, fill=(200, 80, 0))
    p4 = os.path.join(output_dir, "step4_labels.png")
    img4.save(p4)
    paths.append(p4)

    # Step 5: Assignments (lines from labels to elements)
    img5 = img4.copy()
    draw5 = ImageDraw.Draw(img5, 'RGBA')
    for comp in components:
        lc = (comp.label.center[0] * scale, comp.label.center[1] * scale)
        # Gap fill connections
        for gap in comp.gap_fills:
            gc = (gap.center[0] * scale, gap.center[1] * scale)
            draw5.line([lc, gc], fill=(0, 100, 255, 200), width=2)
        # Line end connections
        for end in comp.line_ends:
            ec = (end.position[0] * scale, end.position[1] * scale)
            draw5.line([lc, ec], fill=(0, 200, 100, 200), width=2)
    p5 = os.path.join(output_dir, "step5_assignments.png")
    img5.save(p5)
    paths.append(p5)

    # Step 6: Final components with colored bounding boxes
    img6 = base.copy()
    draw6 = ImageDraw.Draw(img6, 'RGBA')

    # Draw structural groups lightly
    if structural_groups:
        for group in structural_groups:
            color_hex = group.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            for elem in group.elements:
                if elem.start_point and elem.end_point:
                    start = (elem.start_point.x * scale, elem.start_point.y * scale)
                    end = (elem.end_point.x * scale, elem.end_point.y * scale)
                    draw6.line([start, end], fill=(r, g, b, 100), width=1)

    # Draw components (now including those with line_ends)
    for comp in components:
        if comp.gap_fills or comp.circle_pins or comp.line_ends:
            x0, y0, x1, y1 = [c * scale for c in comp.bounding_box]
            color_hex = comp.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            draw6.rectangle([x0, y0, x1, y1],
                           fill=(r, g, b, 60),
                           outline=(r, g, b),
                           width=3)
            draw6.text((x0, y0 - 16), comp.name, fill=(r//2, g//2, b//2))

    p6 = os.path.join(output_dir, "step6_components.png")
    img6.save(p6)
    paths.append(p6)

    print(f"Created {len(paths)} step images in {output_dir}")
    return paths
