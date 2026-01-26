"""
Wire Annotation Reader - Extracts annotations along wires leading to terminals.

Captures:
- Signal names (P24.i2, N24.i, PE, L+, M)
- Destination references (/6.4, /13.34)
- Wire specifications (3x1,5mm Cu)
- Color codes (WH, BN, GN)
- Component references (=070, =077)
"""
import logging
import math
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

from p8_analyzer.core.models import StructuralGroup
from p8_analyzer.core.session import (
    WireAnnotation,
    WireAnnotationType,
    classify_annotation,
    ANNOTATION_PATTERNS,
)
from p8_analyzer.text.hybrid_engine import HybridTextEngine, SearchDirection

logger = logging.getLogger(__name__)


@dataclass
class WireAnnotationConfig:
    """Configuration for wire annotation detection."""
    # Search distance along wire path
    max_search_distance: float = 150.0  # PDF units
    min_search_distance: float = 15.0   # Skip immediate terminal area (label zone)

    # Lateral tolerance (perpendicular to wire)
    lateral_tolerance: float = 12.0

    # Distance between sample points along wire
    sample_step: float = 25.0

    # Connection tolerance for finding wire endpoints
    connection_tolerance: float = 5.0


def _build_combined_pattern() -> str:
    """Build combined regex pattern for all annotation types."""
    all_patterns = []
    for patterns in ANNOTATION_PATTERNS.values():
        all_patterns.extend(patterns)
    return '|'.join(f'({p})' for p in all_patterns)


def _angle_to_direction_name(angle_rad: float) -> str:
    """Convert angle (radians) to direction name."""
    angle_deg = math.degrees(angle_rad) % 360
    if angle_deg < 0:
        angle_deg += 360

    if 315 <= angle_deg or angle_deg < 45:
        return 'right'
    elif 45 <= angle_deg < 135:
        return 'bottom'
    elif 135 <= angle_deg < 225:
        return 'left'
    else:
        return 'top'


def find_connected_paths(
    cx: float,
    cy: float,
    group: StructuralGroup,
    tolerance: float = 5.0
) -> List[Dict]:
    """
    Find wire segments connected to terminal at (cx, cy).

    Args:
        cx, cy: Terminal center coordinates
        group: StructuralGroup containing wire elements
        tolerance: Connection tolerance in PDF units

    Returns:
        List of path info dicts:
        - direction_angle: Angle from terminal (radians)
        - length: Path segment length
        - end_point: Far end of the wire segment (x, y)
    """
    paths = []

    for elem in group.elements:
        start = (elem.start_point.x, elem.start_point.y)
        end = (elem.end_point.x, elem.end_point.y)

        start_dist = math.sqrt((start[0] - cx)**2 + (start[1] - cy)**2)
        end_dist = math.sqrt((end[0] - cx)**2 + (end[1] - cy)**2)

        if start_dist <= tolerance:
            # Wire goes from terminal at start toward end
            angle = math.atan2(end[1] - cy, end[0] - cx)
            length = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
            paths.append({
                'direction_angle': angle,
                'length': length,
                'end_point': end
            })
        elif end_dist <= tolerance:
            # Wire goes from terminal at end toward start
            angle = math.atan2(start[1] - cy, start[0] - cx)
            length = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
            paths.append({
                'direction_angle': angle,
                'length': length,
                'end_point': start
            })

    return paths


def create_cardinal_paths(cx: float, cy: float, length: float = 150.0) -> List[Dict]:
    """
    Create virtual paths in 4 cardinal directions.

    Used when terminal has no associated structural group.

    Args:
        cx, cy: Terminal center coordinates
        length: Search length in each direction

    Returns:
        List of path info dicts for left, right, top, bottom
    """
    return [
        {'direction_angle': 0, 'length': length, 'end_point': (cx + length, cy)},           # right
        {'direction_angle': math.pi, 'length': length, 'end_point': (cx - length, cy)},     # left
        {'direction_angle': -math.pi/2, 'length': length, 'end_point': (cx, cy - length)},  # top
        {'direction_angle': math.pi/2, 'length': length, 'end_point': (cx, cy + length)},   # bottom
    ]


class WireAnnotationReader:
    """
    Reads annotations along wires leading to terminals.

    Algorithm:
    1. For each terminal, find the connected structural group (wire net)
    2. Trace the wire path from the terminal outward
    3. Search for text along the wire path
    4. Classify and return found annotations
    """

    def __init__(self, config: WireAnnotationConfig = None):
        self.config = config or WireAnnotationConfig()
        self._combined_pattern = _build_combined_pattern()

    def read_annotations(
        self,
        terminals: List[Dict],
        structural_groups: List[StructuralGroup],
        text_engine: HybridTextEngine
    ) -> List[Dict]:
        """
        Read wire annotations for all terminals.

        Args:
            terminals: List of terminal dictionaries (with 'center' and 'group_id')
            structural_groups: List of StructuralGroup from vector analysis
            text_engine: HybridTextEngine loaded with current page

        Returns:
            Updated terminals list with 'wire_annotations' field
        """
        if not terminals:
            return terminals

        # Build group lookup
        group_lookup = {g.group_id: g for g in structural_groups}

        for terminal in terminals:
            annotations = self._find_annotations_for_terminal(
                terminal, group_lookup, text_engine
            )
            terminal['wire_annotations'] = [
                self._annotation_to_dict(ann) for ann in annotations
            ]

        # Log statistics
        annotated = sum(1 for t in terminals if t.get('wire_annotations'))
        total_annotations = sum(len(t.get('wire_annotations', [])) for t in terminals)
        logger.info(
            f"Found {total_annotations} wire annotations for "
            f"{annotated}/{len(terminals)} terminals"
        )

        return terminals

    def _find_annotations_for_terminal(
        self,
        terminal: Dict,
        group_lookup: Dict[int, StructuralGroup],
        text_engine: HybridTextEngine
    ) -> List[WireAnnotation]:
        """Find all wire annotations for a single terminal."""
        annotations = []

        center = terminal.get('center', (0, 0))
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            cx, cy = center[0], center[1]
        else:
            return annotations

        group_id = terminal.get('group_id')
        group = group_lookup.get(group_id) if group_id is not None else None

        if group and group.elements:
            # Find wire paths connected to this terminal
            wire_paths = find_connected_paths(
                cx, cy, group, self.config.connection_tolerance
            )
        else:
            # No group info - create 4 virtual paths (left, right, up, down)
            wire_paths = create_cardinal_paths(cx, cy, self.config.max_search_distance)

        for path_info in wire_paths:
            path_annotations = self._search_along_path(
                cx, cy, path_info, text_engine
            )
            annotations.extend(path_annotations)

        # Deduplicate by text content (keep closest to terminal)
        return self._deduplicate_annotations(annotations)

    def _search_along_path(
        self,
        cx: float,
        cy: float,
        path_info: Dict,
        text_engine: HybridTextEngine
    ) -> List[WireAnnotation]:
        """Search for text along a wire path."""
        annotations = []

        direction_rad = path_info['direction_angle']
        direction_name = _angle_to_direction_name(direction_rad)
        max_dist = min(path_info['length'], self.config.max_search_distance)

        # Track already found text positions to avoid duplicates within this path
        found_positions: Set[Tuple[float, float]] = set()

        distance = self.config.min_search_distance
        while distance <= max_dist:
            # Calculate sample point along path
            sample_x = cx + distance * math.cos(direction_rad)
            sample_y = cy + distance * math.sin(direction_rad)

            # Search for text near sample point
            found_texts = text_engine.find_all_text_near(
                point=(sample_x, sample_y),
                radius=self.config.lateral_tolerance,
                pattern=None,  # Get all text, filter later
                direction=SearchDirection.ANY
            )

            for text_elem in found_texts:
                # Skip if already found at this position
                pos_key = (round(text_elem.center[0], 1), round(text_elem.center[1], 1))
                if pos_key in found_positions:
                    continue

                # Check if text matches any annotation pattern
                ann_type = classify_annotation(text_elem.text)
                if ann_type == WireAnnotationType.UNKNOWN:
                    continue

                found_positions.add(pos_key)

                # Calculate distance from terminal to text
                text_cx, text_cy = text_elem.center
                dist_to_terminal = math.sqrt((text_cx - cx)**2 + (text_cy - cy)**2)

                annotation = WireAnnotation(
                    text=text_elem.text,
                    position_x=text_cx,
                    position_y=text_cy,
                    annotation_type=ann_type,
                    distance_to_terminal=dist_to_terminal,
                    direction=direction_name,
                    source=text_elem.source,
                    confidence=text_elem.confidence
                )
                annotations.append(annotation)

            distance += self.config.sample_step

        return annotations

    def _deduplicate_annotations(
        self,
        annotations: List[WireAnnotation]
    ) -> List[WireAnnotation]:
        """
        Keep only unique texts, preferring closest to terminal.

        Args:
            annotations: List of WireAnnotation objects

        Returns:
            Deduplicated list
        """
        seen: Dict[str, WireAnnotation] = {}

        # Sort by distance to terminal (closest first)
        sorted_anns = sorted(annotations, key=lambda a: a.distance_to_terminal)

        for ann in sorted_anns:
            if ann.text not in seen:
                seen[ann.text] = ann

        return list(seen.values())

    def _annotation_to_dict(self, ann: WireAnnotation) -> Dict:
        """Convert WireAnnotation to dictionary for storage in terminal dict."""
        return {
            'text': ann.text,
            'position_x': ann.position_x,
            'position_y': ann.position_y,
            'annotation_type': ann.annotation_type.value,
            'distance_to_terminal': ann.distance_to_terminal,
            'direction': ann.direction,
            'source': ann.source,
            'confidence': ann.confidence
        }
