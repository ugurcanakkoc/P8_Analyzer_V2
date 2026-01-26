"""
Unified Analysis Engine - Shared by CLI and GUI.

This module contains all analysis logic that should be identical
between CLI and GUI usage.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

import pymupdf

from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG
from p8_analyzer.core.session import (
    PageAnalysis,
    Terminal,
    Component,
    Pin,
    Connection,
    WireAnnotation,
)
from p8_analyzer.detection import (
    TerminalDetector,
    TerminalReader,
    TerminalGrouper,
    ClusterDetector,
    WireAnnotationReader,
    PinFinder,
    get_default_settings,
)
from p8_analyzer.text import HybridTextEngine
from p8_analyzer.circuit import check_intersections, CircuitComponent

logger = logging.getLogger(__name__)


@dataclass
class AnalysisOptions:
    """Configuration options for page analysis."""
    include_terminals: bool = True
    include_clusters: bool = True
    include_wire_annotations: bool = True
    include_connections: bool = True
    include_pins: bool = True
    languages: List[str] = field(default_factory=lambda: ['en', 'de'])


class AnalysisEngine:
    """
    Unified analysis engine for P8 electrical schematics.

    Used by both CLI and GUI for consistent results.
    """

    def __init__(self, options: AnalysisOptions = None):
        self.options = options or AnalysisOptions()
        self._text_engine = None
        self._analysis_result = None

    def analyze_page(
        self,
        page: pymupdf.Page,
        page_num: int
    ) -> PageAnalysis:
        """
        Analyze a single page and return complete PageAnalysis.

        Args:
            page: PyMuPDF page object
            page_num: Page number (1-indexed)

        Returns:
            PageAnalysis with terminals, components, connections, and annotations
        """
        # Get page dimensions
        rect = page.rect
        page_width = rect.width
        page_height = rect.height

        # Vector analysis
        drawings = page.get_drawings()
        if not drawings:
            logger.warning(f"No vector data found on page {page_num}")
            return PageAnalysis(
                page_number=page_num,
                page_width=page_width,
                page_height=page_height
            )

        self._analysis_result = analyze_page_vectors(
            drawings, page.rect, page_num, DEFAULT_CONFIG
        )

        # Initialize text engine
        self._text_engine = HybridTextEngine(languages=self.options.languages)
        self._text_engine.load_page(page)

        # Step 1: Terminal detection
        terminals_raw = []
        if self.options.include_terminals:
            terminals_raw = self._detect_terminals()

        # Step 2: Component/cluster detection
        components_raw = []
        cluster_boxes = []
        if self.options.include_clusters:
            components_raw, cluster_boxes = self._detect_components(page)

        # Step 3: Wire annotation detection
        if self.options.include_wire_annotations and terminals_raw:
            terminals_raw = self._detect_wire_annotations(terminals_raw)

        # Step 4: Pin detection inside components
        pins_by_component = {}
        if self.options.include_pins and cluster_boxes:
            pins_by_component = self._detect_pins(cluster_boxes)

        # Step 5: Connection detection
        connections_raw = []
        if self.options.include_connections:
            connections_raw = self._detect_connections(
                terminals_raw, cluster_boxes, pins_by_component
            )

        # Convert to Pydantic models
        terminal_models = [
            self._terminal_to_model(t, page_num) for t in terminals_raw
        ]
        component_models = [
            self._component_to_model(c, page_num, pins_by_component)
            for c in components_raw
        ]
        connection_models = [
            self._connection_to_model(c) for c in connections_raw
        ]

        return PageAnalysis(
            page_number=page_num,
            page_width=page_width,
            page_height=page_height,
            terminals=terminal_models,
            components=component_models,
            connections=connection_models,
            structural_group_count=len(self._analysis_result.structural_groups),
            analysis_timestamp=datetime.now()
        )

    def _detect_terminals(self) -> List[Dict]:
        """Detect and read terminal labels."""
        try:
            detector = TerminalDetector()
            terminals = detector.detect(self._analysis_result)

            if terminals:
                reader = TerminalReader()
                terminals = reader.read_labels(terminals, self._text_engine)

                grouper = TerminalGrouper()
                terminals = grouper.group_terminals(terminals, self._text_engine)

            return terminals

        except Exception as e:
            logger.error(f"Terminal detection error: {e}")
            return []

    def _detect_components(
        self,
        page: pymupdf.Page
    ) -> Tuple[List[Dict], List[CircuitComponent]]:
        """
        Detect component clusters and convert to CircuitComponent boxes.

        Returns:
            Tuple of (raw component dicts, CircuitComponent boxes for pin finding)
        """
        try:
            settings = get_default_settings()
            cluster_detector = ClusterDetector(
                vertical_weight=settings.vertical_weight,
                absolute_min_gap=settings.absolute_min_gap,
                density_factor=settings.density_factor,
                max_gap=settings.max_gap,
                label_max_distance=settings.label_max_distance,
                label_cluster_size_factor=settings.label_cluster_size_factor,
                cross_color_penalty=settings.cross_color_penalty,
                label_subsume_threshold=settings.label_subsume_threshold
            )

            clusters, labels, gap_fills, circle_pins, line_ends = \
                cluster_detector.detect_clusters(
                    page,
                    self._analysis_result.broken_connections,
                    self._analysis_result.structural_groups
                )

            # Convert to raw component dicts and CircuitComponent boxes
            components = []
            cluster_boxes = []

            for cluster in clusters:
                label_text = None
                if cluster.label:
                    label_text = getattr(cluster.label, 'text', str(cluster.label))

                comp = {
                    'bbox': cluster.bbox,
                    'label': label_text,
                    'objects': cluster.objects,
                    'pins': []
                }
                components.append(comp)

                # Create CircuitComponent for labeled clusters (for pin finding)
                if label_text:
                    circuit_comp = CircuitComponent(
                        id=label_text,
                        label=label_text,
                        bbox={
                            'min_x': cluster.bbox[0],
                            'min_y': cluster.bbox[1],
                            'max_x': cluster.bbox[2],
                            'max_y': cluster.bbox[3]
                        }
                    )
                    cluster_boxes.append(circuit_comp)

            logger.info(f"Detected {len(components)} components, {len(cluster_boxes)} with labels")

            # Store clusters for pin detection
            self._clusters = clusters

            return components, cluster_boxes

        except Exception as e:
            logger.error(f"Component detection error: {e}")
            return [], []

    def _detect_wire_annotations(self, terminals: List[Dict]) -> List[Dict]:
        """Detect wire annotations along paths to terminals."""
        try:
            annotation_reader = WireAnnotationReader()
            terminals = annotation_reader.read_annotations(
                terminals,
                self._analysis_result.structural_groups,
                self._text_engine
            )
            return terminals

        except Exception as e:
            logger.error(f"Wire annotation detection error: {e}")
            return terminals

    def _detect_pins(
        self,
        cluster_boxes: List[CircuitComponent]
    ) -> Dict[str, List[Dict]]:
        """
        Detect labels for ClusterObjects (gaps, circles, line_ends) in each cluster.

        For gaps: uses gap_start and gap_end positions
        For circles/line_ends: uses the object position

        Returns:
            Dict mapping component ID to list of labeled connection points
        """
        import math
        pins_by_component = {}

        if not hasattr(self, '_clusters') or not self._clusters:
            return pins_by_component

        # Build map of component label -> cluster
        label_to_cluster = {}
        for cluster in self._clusters:
            if cluster.label:
                label_text = getattr(cluster.label, 'text', str(cluster.label))
                label_to_cluster[label_text] = cluster

        # For each labeled cluster, find labels for all ClusterObjects
        for comp_label, cluster in label_to_cluster.items():
            pins = []
            used_text_positions = set()  # Avoid duplicate labels

            # For each ClusterObject in the cluster
            for obj in cluster.objects:
                # Get all connection points for this object
                points = self._get_cluster_object_points(obj)

                for px, py in points:
                    # Find nearest text label
                    label_result = self._find_nearest_label(px, py, radius=15.0)

                    if label_result:
                        text, tx, ty = label_result

                        # Check if we already found this text (by position)
                        text_key = (round(tx, 1), round(ty, 1))
                        if text_key in used_text_positions:
                            continue
                        used_text_positions.add(text_key)

                        full_label = f"{comp_label}:{text}"
                        pins.append({
                            'pin_label': text,
                            'full_label': full_label,
                            'location': (px, py),
                            'box_id': comp_label
                        })

            if pins:
                pins_by_component[comp_label] = pins

        total_pins = sum(len(pins) for pins in pins_by_component.values())
        logger.info(f"Detected {total_pins} connection labels across {len(pins_by_component)} components")

        return pins_by_component

    def _detect_endpoint_labels(self) -> Dict[int, List[Dict]]:
        """
        Detect text labels at wire endpoints in unlabeled clusters.

        These are signal names like 'L1', 'L2', 'PE' that appear at line terminators
        but aren't associated with a component.

        Returns:
            Dict mapping structural_group_index -> list of endpoint label dicts
        """
        import math
        endpoint_labels = {}

        if not hasattr(self, '_clusters') or not self._clusters:
            return endpoint_labels

        # Get labeled cluster labels to skip
        labeled_cluster_labels = set()
        for cluster in self._clusters:
            if cluster.label:
                labeled_cluster_labels.add(getattr(cluster.label, 'text', str(cluster.label)))

        # For unlabeled clusters, find labels at endpoints
        for cluster in self._clusters:
            if cluster.label:
                continue  # Skip labeled clusters (handled by _detect_pins)

            for obj in cluster.objects:
                points = self._get_cluster_object_points(obj)

                for px, py in points:
                    # Find text label near this endpoint
                    label_result = self._find_nearest_label(px, py, radius=15.0)

                    if label_result:
                        text, tx, ty = label_result

                        # Find which structural group this point belongs to
                        group_idx = self._find_structural_group_for_point(px, py)

                        if group_idx is not None:
                            if group_idx not in endpoint_labels:
                                endpoint_labels[group_idx] = []

                            # Check for duplicates
                            existing = [e['label'] for e in endpoint_labels[group_idx]]
                            if text not in existing:
                                endpoint_labels[group_idx].append({
                                    'label': text,
                                    'location': (px, py),
                                    'text_location': (tx, ty)
                                })

        total_labels = sum(len(labels) for labels in endpoint_labels.values())
        if total_labels > 0:
            logger.info(f"Detected {total_labels} endpoint labels in unlabeled clusters")

        return endpoint_labels

    def _find_structural_group_for_point(self, x: float, y: float, tolerance: float = 5.0) -> Optional[int]:
        """Find which structural group a point belongs to."""
        import math

        for i, group in enumerate(self._analysis_result.structural_groups):
            for elem in group.elements:
                # Check distance to start and end points
                for pt in [elem.start_point, elem.end_point]:
                    dist = math.sqrt((pt.x - x)**2 + (pt.y - y)**2)
                    if dist < tolerance:
                        return i

        return None

    def _get_cluster_object_points(self, obj) -> List[Tuple[float, float]]:
        """Get all connection points from a ClusterObject."""
        points = []

        if obj.obj_type == 'gap':
            # Gap has start and end points
            orig = obj.original
            if hasattr(orig, 'gap_start') and orig.gap_start:
                points.append((orig.gap_start[0], orig.gap_start[1]))
            if hasattr(orig, 'gap_end') and orig.gap_end:
                points.append((orig.gap_end[0], orig.gap_end[1]))
        else:
            # Circle and line_end use position
            points.append(obj.position)

        return points

    def _find_nearest_label(self, x: float, y: float, radius: float):
        """Find nearest valid label text within radius of point."""
        import math
        best = None
        best_dist = radius

        for elem in self._text_engine.pdf_elements:
            text = elem.text.strip()
            if not self._is_valid_pin_label(text):
                continue

            tx, ty = elem.center
            dist = math.sqrt((tx - x)**2 + (ty - y)**2)

            if dist < best_dist:
                best_dist = dist
                best = (text, tx, ty)

        return best

    def _is_valid_pin_label(self, label: str) -> bool:
        """Check if text is a valid pin/connection label."""
        if not label:
            return False
        if len(label) > 10:
            return False
        # Skip component labels (start with -)
        if label.startswith('-'):
            return False
        return True

    def _order_along_wire_path(self, comp_ids: List[str], group, terminals: List[Dict],
                                pins_by_component: Dict[str, List[Dict]],
                                endpoint_labels: List[Dict] = None) -> List[str]:
        """
        Order connection elements along the wire path using the structural group's element order.

        The structural group's elements are ALREADY in wire order from vector analysis.
        We walk through elements in order and output components as we encounter them.
        NO position-based sorting - just use the element order directly.

        Args:
            comp_ids: List of component/terminal/pin IDs in this network
            group: StructuralGroup representing the wire path (elements already in order)
            terminals: Terminal dicts with positions
            pins_by_component: Pins organized by component
            endpoint_labels: Labels at wire endpoints in unlabeled clusters

        Returns:
            Ordered list of IDs following the wire path
        """
        import math

        if endpoint_labels is None:
            endpoint_labels = []

        # Track which components have pins in this network
        comps_with_pins = set()
        for comp_id in comp_ids:
            if ':' in comp_id:
                base_comp = comp_id.rsplit(':', 1)[0]
                comps_with_pins.add(base_comp)

        # Filter out redundant component entries (component without pin when pins exist)
        filtered_ids = set()
        for comp_id in comp_ids:
            # If this is a bare component (no pin) and it has pins in the network, skip it
            if ':' not in comp_id and comp_id in comps_with_pins:
                continue
            filtered_ids.add(comp_id)

        # If no group or less than 2 elements, return as-is
        if not filtered_ids:
            return []
        if len(filtered_ids) <= 1 or group is None or not hasattr(group, 'elements'):
            return list(filtered_ids)

        # Build position map for all elements
        positions = {}

        # Add terminal positions
        for term in terminals:
            label = term.get('full_label') or term.get('group_label') or ''
            if label and label in filtered_ids:
                cx, cy = term['center']
                positions[label] = (cx, cy)

        # Add pin positions
        for comp_id, pins in pins_by_component.items():
            for pin in pins:
                full_label = pin['full_label']
                if full_label in filtered_ids:
                    positions[full_label] = pin['location']

        # Add component positions (only for components without pins)
        if hasattr(self, '_clusters'):
            for cluster in self._clusters:
                if cluster.label:
                    label_text = getattr(cluster.label, 'text', str(cluster.label))
                    if label_text in filtered_ids and label_text not in positions:
                        positions[label_text] = cluster.center

        # Add endpoint label positions (signal names at line terminators)
        for label_info in endpoint_labels:
            label = label_info['label']
            if label in filtered_ids and label not in positions:
                positions[label] = label_info['location']

        # Walk through group.elements in order and collect components as we encounter them
        TOLERANCE = 8.0
        ordered = []
        seen = set()

        def find_comp_at_point(px, py):
            """Find closest component/pin/terminal at this point."""
            best_comp = None
            best_dist = TOLERANCE
            for comp_id, (cx, cy) in positions.items():
                if comp_id in seen:
                    continue
                dist = math.sqrt((px - cx)**2 + (py - cy)**2)
                if dist < best_dist:
                    best_dist = dist
                    best_comp = comp_id
            return best_comp

        # Walk through each element's start and end points in order
        for elem in group.elements:
            # Check start point
            comp = find_comp_at_point(elem.start_point.x, elem.start_point.y)
            if comp and comp not in seen:
                ordered.append(comp)
                seen.add(comp)

            # Check end point
            comp = find_comp_at_point(elem.end_point.x, elem.end_point.y)
            if comp and comp not in seen:
                ordered.append(comp)
                seen.add(comp)

        # Add any remaining components that weren't found along the path
        for comp_id in filtered_ids:
            if comp_id not in seen:
                ordered.append(comp_id)

        return ordered

    def _detect_connections(
        self,
        terminals: List[Dict],
        cluster_boxes: List[CircuitComponent],
        pins_by_component: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Detect connections between terminals, components, and pins.

        Returns:
            List of connection dicts with source, target, and net_id
        """
        import math
        connections = []

        try:
            # Create terminal components for intersection checking
            terminal_comps = []
            for term in terminals:
                cx, cy = term['center']
                # Use full_label, group_label, label, or skip if all empty
                label = term.get('full_label') or term.get('group_label') or term.get('label') or ''
                if not label:
                    continue  # Skip unlabeled terminals in connection checking
                comp = CircuitComponent(
                    id=label,
                    label='Terminal',
                    bbox={'min_x': cx-2, 'min_y': cy-2, 'max_x': cx+2, 'max_y': cy+2}
                )
                terminal_comps.append(comp)

            # All components for intersection checking
            all_comps = cluster_boxes + terminal_comps

            # Check intersections
            net_connections = check_intersections(all_comps, self._analysis_result)

            # Add pins to their networks based on pin location matching structural group
            # Also track element index for ordering
            component_element_idx = {}  # comp_id -> element index in group

            for i, group in enumerate(self._analysis_result.structural_groups):
                net_id = f'NET-{i+1:03d}'

                # Build element index lookup: point -> minimum element index
                # At junctions, multiple elements share the same point - use minimum index
                point_to_elem_idx = {}
                for elem_idx, elem in enumerate(group.elements):
                    sp = (round(elem.start_point.x, 1), round(elem.start_point.y, 1))
                    ep = (round(elem.end_point.x, 1), round(elem.end_point.y, 1))
                    # For start point, use elem_idx * 2; for end point, use elem_idx * 2 + 1
                    start_idx = elem_idx * 2
                    end_idx = elem_idx * 2 + 1
                    # Keep minimum index at each point (junction handling)
                    if sp not in point_to_elem_idx or start_idx < point_to_elem_idx[sp]:
                        point_to_elem_idx[sp] = start_idx
                    if ep not in point_to_elem_idx or end_idx < point_to_elem_idx[ep]:
                        point_to_elem_idx[ep] = end_idx

                # Check which pins are on this group
                for comp_id, pins in pins_by_component.items():
                    for pin in pins:
                        px, py = pin['location']

                        # Find closest element point
                        best_idx = None
                        best_dist = 5.0
                        for (gx, gy), idx in point_to_elem_idx.items():
                            dist = math.sqrt((px - gx)**2 + (py - gy)**2)
                            if dist < best_dist:
                                best_dist = dist
                                best_idx = idx

                        if best_idx is not None:
                            net_connections.setdefault(net_id, []).append(pin['full_label'])
                            component_element_idx[(net_id, pin['full_label'])] = best_idx

            # Add endpoint labels from unlabeled clusters (signal names at line terminators)
            endpoint_labels = self._detect_endpoint_labels()
            for group_idx, labels in endpoint_labels.items():
                net_id = f'NET-{group_idx+1:03d}'
                group = self._analysis_result.structural_groups[group_idx]

                # Build element index lookup for this group
                # At junctions, multiple elements share the same point - use minimum index
                point_to_elem_idx = {}
                for elem_idx, elem in enumerate(group.elements):
                    sp = (round(elem.start_point.x, 1), round(elem.start_point.y, 1))
                    ep = (round(elem.end_point.x, 1), round(elem.end_point.y, 1))
                    start_idx = elem_idx * 2
                    end_idx = elem_idx * 2 + 1
                    if sp not in point_to_elem_idx or start_idx < point_to_elem_idx[sp]:
                        point_to_elem_idx[sp] = start_idx
                    if ep not in point_to_elem_idx or end_idx < point_to_elem_idx[ep]:
                        point_to_elem_idx[ep] = end_idx

                for label_info in labels:
                    net_connections.setdefault(net_id, []).append(label_info['label'])
                    # Find element index for this label
                    lx, ly = label_info['location']
                    best_idx = len(group.elements) * 2  # Default to end
                    best_dist = 10.0
                    for (gx, gy), idx in point_to_elem_idx.items():
                        dist = math.sqrt((lx - gx)**2 + (ly - gy)**2)
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = idx
                    component_element_idx[(net_id, label_info['label'])] = best_idx

            # Also track element index for terminals from check_intersections
            for net_id, comp_ids in net_connections.items():
                group_idx = int(net_id.split('-')[1]) - 1
                if 0 <= group_idx < len(self._analysis_result.structural_groups):
                    group = self._analysis_result.structural_groups[group_idx]

                    # Build element index lookup
                    # At junctions, multiple elements share the same point - use minimum index
                    point_to_elem_idx = {}
                    for elem_idx, elem in enumerate(group.elements):
                        sp = (round(elem.start_point.x, 1), round(elem.start_point.y, 1))
                        ep = (round(elem.end_point.x, 1), round(elem.end_point.y, 1))
                        start_idx = elem_idx * 2
                        end_idx = elem_idx * 2 + 1
                        if sp not in point_to_elem_idx or start_idx < point_to_elem_idx[sp]:
                            point_to_elem_idx[sp] = start_idx
                        if ep not in point_to_elem_idx or end_idx < point_to_elem_idx[ep]:
                            point_to_elem_idx[ep] = end_idx

                    for comp_id in comp_ids:
                        if (net_id, comp_id) in component_element_idx:
                            continue  # Already have index

                        # Find position for this component
                        pos = None
                        for term in terminals:
                            label = term.get('full_label') or term.get('group_label') or ''
                            if label == comp_id:
                                pos = term['center']
                                break

                        if pos:
                            cx, cy = pos
                            best_idx = 0
                            best_dist = 10.0
                            for (gx, gy), idx in point_to_elem_idx.items():
                                dist = math.sqrt((cx - gx)**2 + (cy - gy)**2)
                                if dist < best_dist:
                                    best_dist = dist
                                    best_idx = idx
                            component_element_idx[(net_id, comp_id)] = best_idx

            # Convert to connection list with ordered path
            for net_id, comp_ids in net_connections.items():
                if len(comp_ids) >= 2:
                    unique_ids = list(dict.fromkeys(comp_ids))  # Remove duplicates

                    # Order by element index (wire traversal order)
                    def get_elem_idx(comp_id):
                        return component_element_idx.get((net_id, comp_id), 999999)

                    ordered_ids = sorted(unique_ids, key=get_elem_idx)

                    # Create sequential connections along the path
                    for i in range(len(ordered_ids) - 1):
                        connections.append({
                            'source': ordered_ids[i],
                            'target': ordered_ids[i + 1],
                            'net_id': net_id,
                            'all_connected': ordered_ids
                        })

            logger.info(f"Detected {len(connections)} connections")

        except Exception as e:
            logger.error(f"Connection detection error: {e}")

        return connections

    def _terminal_to_model(self, terminal: Dict, page_num: int) -> Terminal:
        """Convert terminal dict to Terminal Pydantic model."""
        center = terminal.get('center', (0, 0))
        cx, cy = center[0], center[1]

        label = terminal.get('label')
        group_label = terminal.get('group_label')
        full_label = terminal.get('full_label')

        # Build terminal_id without UNK placeholders
        group_part = group_label or ""
        label_part = label or ""
        terminal_id = f"{page_num}_{group_part}_{label_part}".strip("_")

        wire_anns = []
        for ann in terminal.get('wire_annotations', []):
            wire_anns.append(WireAnnotation(
                text=ann['text'],
                position_x=ann['position_x'],
                position_y=ann['position_y'],
                annotation_type=ann['annotation_type'],
                distance_to_terminal=ann['distance_to_terminal'],
                direction=ann['direction'],
                source=ann.get('source', 'pdf'),
                confidence=ann.get('confidence', 1.0)
            ))

        return Terminal(
            id=terminal_id,
            center_x=cx,
            center_y=cy,
            radius=terminal.get('radius', 3.0),
            label=label,
            label_source=terminal.get('label_source'),
            group_label=group_label,
            group_source=terminal.get('group_source'),
            full_label=full_label,
            structural_group_id=terminal.get('group_id'),
            wire_annotations=wire_anns
        )

    def _component_to_model(
        self,
        component: Dict,
        page_num: int,
        pins_by_component: Dict[str, List[Dict]]
    ) -> Component:
        """Convert component dict to Component Pydantic model."""
        bbox = component.get('bbox', (0, 0, 0, 0))
        label = component.get('label')

        comp_id = f"{page_num}_{label or 'COMP'}_{hash(str(bbox)) % 10000}"

        # Get pins for this component
        pins = []
        if label and label in pins_by_component:
            for pin in pins_by_component[label]:
                loc = pin.get('location', (0, 0))
                pins.append(Pin(
                    label=pin.get('pin_label', ''),
                    position_x=loc[0],
                    position_y=loc[1]
                ))

        return Component(
            id=comp_id,
            label=label,
            component_type=component.get('component_type'),
            bbox_min_x=bbox[0],
            bbox_min_y=bbox[1],
            bbox_max_x=bbox[2],
            bbox_max_y=bbox[3],
            pins=pins
        )

    def _connection_to_model(self, connection: Dict) -> Connection:
        """Convert connection dict to Connection Pydantic model."""
        return Connection(
            source_id=connection['source'],
            target_id=connection['target'],
            net_id=connection['net_id'],
            wire_annotations=[]
        )
