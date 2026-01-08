"""
Experimental: Clustering-based Component Detection

Uses density-aware agglomerative clustering to group circuit objects
(gap fills, circle pins, line ends) into components, then matches labels.

Key features:
- No fixed cluster count
- Adaptive merge threshold based on internal cluster density
- Vertical distance penalized more than horizontal
- Keeps unlabeled clusters as anonymous components
"""

import math
from typing import List, Dict, Tuple, Optional, Set, Union
from dataclasses import dataclass, field
import pymupdf
from PIL import Image, ImageDraw

from .label_detector import LabelDetector, DetectedLabel
from .component_detector import (
    FilteredGapFill, FilteredCirclePin, FilteredLineEnd,
    ComponentDetector
)
from ..core.models import StructuralGroup, BrokenConnection


@dataclass
class ClusterObject:
    """A single object that can be clustered."""
    position: Tuple[float, float]
    obj_type: str  # 'gap', 'circle', 'line_end'
    color: str
    original: Union[FilteredGapFill, FilteredCirclePin, FilteredLineEnd]

    def get_bbox(self, padding: float = 2.0) -> Tuple[float, float, float, float]:
        """Get bounding box as (x0, y0, x1, y1)."""
        x, y = self.position
        return (x - padding, y - padding, x + padding, y + padding)


@dataclass
class ObjectCluster:
    """A cluster of objects that may form a component."""
    cluster_id: int
    objects: List[ClusterObject] = field(default_factory=list)
    label: Optional[DetectedLabel] = None

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Calculate bounding box of all objects in cluster."""
        if not self.objects:
            return (0, 0, 0, 0)

        x_coords = [o.position[0] for o in self.objects]
        y_coords = [o.position[1] for o in self.objects]

        padding = 5.0
        return (
            min(x_coords) - padding,
            min(y_coords) - padding,
            max(x_coords) + padding,
            max(y_coords) + padding
        )

    @property
    def center(self) -> Tuple[float, float]:
        """Get center of cluster."""
        if not self.objects:
            return (0, 0)
        x = sum(o.position[0] for o in self.objects) / len(self.objects)
        y = sum(o.position[1] for o in self.objects) / len(self.objects)
        return (x, y)

    @property
    def primary_color(self) -> str:
        """Get most common color in cluster."""
        if not self.objects:
            return "#00AA00"
        color_counts: Dict[str, int] = {}
        for obj in self.objects:
            color_counts[obj.color] = color_counts.get(obj.color, 0) + 1
        return max(color_counts, key=color_counts.get)

    def average_internal_spacing(self, vertical_weight: float = 3.0) -> float:
        """Calculate average nearest-neighbor distance within cluster."""
        if len(self.objects) < 2:
            return float('inf')

        total_nn_dist = 0.0
        for i, obj_a in enumerate(self.objects):
            min_dist = float('inf')
            for j, obj_b in enumerate(self.objects):
                if i != j:
                    dist = weighted_distance(obj_a.position, obj_b.position, vertical_weight)
                    min_dist = min(min_dist, dist)
            if min_dist < float('inf'):
                total_nn_dist += min_dist

        return total_nn_dist / len(self.objects)


def weighted_distance(p1: Tuple[float, float], p2: Tuple[float, float],
                      vertical_weight: float = 3.0) -> float:
    """Calculate distance with vertical penalty."""
    dx = abs(p1[0] - p2[0])
    dy = abs(p1[1] - p2[1])
    return math.sqrt(dx**2 + (dy * vertical_weight)**2)


def min_cluster_distance(cluster_a: ObjectCluster, cluster_b: ObjectCluster,
                         vertical_weight: float = 3.0) -> float:
    """Find minimum distance between any pair of objects in two clusters."""
    min_dist = float('inf')
    for obj_a in cluster_a.objects:
        for obj_b in cluster_b.objects:
            dist = weighted_distance(obj_a.position, obj_b.position, vertical_weight)
            min_dist = min(min_dist, dist)
    return min_dist


def clusters_share_color(cluster_a: ObjectCluster, cluster_b: ObjectCluster) -> bool:
    """Check if clusters have any objects with matching colors."""
    colors_a = {obj.color for obj in cluster_a.objects}
    colors_b = {obj.color for obj in cluster_b.objects}
    return bool(colors_a & colors_b)


class ClusterDetector:
    """
    Clustering-based component detection.

    Algorithm:
    1. Convert all objects (gaps, pins, line ends) to ClusterObjects
    2. Start with each object as its own cluster
    3. Iteratively merge closest clusters if gap is acceptable
    4. Match labels to clusters
    5. Return all clusters (labeled and unlabeled)
    """

    def __init__(self,
                 vertical_weight: float = 3.0,
                 absolute_min_gap: float = 15.0,
                 density_factor: float = 2.0,
                 max_gap: float = 80.0,
                 label_max_distance: float = 60.0,
                 label_cluster_size_factor: float = 0.5,
                 cross_color_penalty: float = 2.0,
                 label_subsume_threshold: float = 0.5):
        """
        Initialize cluster detector.

        Args:
            vertical_weight: How much more to penalize vertical distance
            absolute_min_gap: Always merge if gap is smaller than this
            density_factor: Merge if gap < internal_spacing * this factor
            max_gap: Never merge if gap exceeds this (weighted distance)
            label_max_distance: Base max distance for label-to-cluster matching
            label_cluster_size_factor: Additional distance allowance per unit of cluster diagonal
            cross_color_penalty: Multiply gap by this for different-color merges
            label_subsume_threshold: Forbid merges that subsume label by more than this fraction
        """
        self.vertical_weight = vertical_weight
        self.absolute_min_gap = absolute_min_gap
        self.density_factor = density_factor
        self.max_gap = max_gap
        self.label_max_distance = label_max_distance
        self.label_cluster_size_factor = label_cluster_size_factor
        self.cross_color_penalty = cross_color_penalty
        self.label_subsume_threshold = label_subsume_threshold
        self.label_detector = LabelDetector()

    def _should_merge(self, cluster_a: ObjectCluster, cluster_b: ObjectCluster,
                      gap_distance: float) -> bool:
        """
        Determine if two clusters should be merged based on distance/density.

        Merge if gap is small relative to internal cluster density.
        Different-color clusters are penalized (effectively need to be closer).
        
        Note: Label subsumption is checked separately in _agglomerative_cluster.
        """
        # Apply color penalty for different-colored clusters
        effective_gap = gap_distance
        same_color = clusters_share_color(cluster_a, cluster_b)
        if not same_color:
            effective_gap *= self.cross_color_penalty

        # Always merge very close clusters (even different colors if very close)
        if effective_gap <= self.absolute_min_gap:
            return True

        # Never merge if effective gap is too large
        if effective_gap > self.max_gap:
            return False

        # Calculate internal spacing of both clusters
        spacing_a = cluster_a.average_internal_spacing(self.vertical_weight)
        spacing_b = cluster_b.average_internal_spacing(self.vertical_weight)

        # Use the smaller internal spacing as reference
        # (merge if gap is similar to how objects are spaced inside)
        if spacing_a == float('inf') and spacing_b == float('inf'):
            # Both are single objects - use absolute threshold
            return effective_gap <= self.absolute_min_gap * 2

        reference_spacing = min(
            spacing_a if spacing_a < float('inf') else spacing_b,
            spacing_b if spacing_b < float('inf') else spacing_a
        )

        # Merge if effective gap is within density_factor of internal spacing
        return effective_gap <= reference_spacing * self.density_factor

    def _merge_would_subsume_label(self, cluster_a: ObjectCluster, cluster_b: ObjectCluster,
                                    labels: List[DetectedLabel]) -> bool:
        """
        Check if merging two clusters would subsume any label beyond threshold.
        
        Returns True if merge should be forbidden due to label subsumption.
        """
        # Calculate merged bounding box
        bbox_a = cluster_a.bbox
        bbox_b = cluster_b.bbox
        merged_bbox = (
            min(bbox_a[0], bbox_b[0]),
            min(bbox_a[1], bbox_b[1]),
            max(bbox_a[2], bbox_b[2]),
            max(bbox_a[3], bbox_b[3])
        )
        
        # Check each label
        for label in labels:
            # Calculate intersection with merged bbox
            lx0, ly0, lx1, ly1 = label.bbox
            ix0 = max(merged_bbox[0], lx0)
            iy0 = max(merged_bbox[1], ly0)
            ix1 = min(merged_bbox[2], lx1)
            iy1 = min(merged_bbox[3], ly1)
            
            # No intersection
            if ix0 >= ix1 or iy0 >= iy1:
                continue
            
            # Calculate intersection area
            intersection_area = (ix1 - ix0) * (iy1 - iy0)
            label_area = (lx1 - lx0) * (ly1 - ly0)
            
            if label_area <= 0:
                continue
            
            subsume_ratio = intersection_area / label_area
            
            # If merge would subsume label beyond threshold, forbid it
            if subsume_ratio > self.label_subsume_threshold:
                # But only forbid if neither cluster alone subsumes the label
                # (i.e., the merge creates the subsumption)
                subsume_a = self._bbox_subsume_ratio(bbox_a, label.bbox)
                subsume_b = self._bbox_subsume_ratio(bbox_b, label.bbox)
                
                if subsume_a <= self.label_subsume_threshold and \
                   subsume_b <= self.label_subsume_threshold:
                    return True
        
        return False
    
    def _bbox_subsume_ratio(self, cluster_bbox: Tuple[float, float, float, float],
                            label_bbox: Tuple[float, float, float, float]) -> float:
        """Calculate what fraction of label is inside cluster bbox."""
        cx0, cy0, cx1, cy1 = cluster_bbox
        lx0, ly0, lx1, ly1 = label_bbox
        
        # Calculate intersection
        ix0 = max(cx0, lx0)
        iy0 = max(cy0, ly0)
        ix1 = min(cx1, lx1)
        iy1 = min(cy1, ly1)
        
        if ix0 >= ix1 or iy0 >= iy1:
            return 0.0
        
        intersection_area = (ix1 - ix0) * (iy1 - iy0)
        label_area = (lx1 - lx0) * (ly1 - ly0)
        
        if label_area <= 0:
            return 0.0
        
        return intersection_area / label_area

    def _objects_from_filtered(self,
                               gap_fills: List[FilteredGapFill],
                               circle_pins: List[FilteredCirclePin],
                               line_ends: List[FilteredLineEnd]
                               ) -> List[ClusterObject]:
        """Convert filtered objects to ClusterObjects."""
        objects = []

        for gap in gap_fills:
            objects.append(ClusterObject(
                position=gap.center,
                obj_type='gap',
                color=gap.color,
                original=gap
            ))

        for pin in circle_pins:
            objects.append(ClusterObject(
                position=pin.center,
                obj_type='circle',
                color=pin.color,
                original=pin
            ))

        for end in line_ends:
            objects.append(ClusterObject(
                position=end.position,
                obj_type='line_end',
                color=end.color,
                original=end
            ))

        return objects

    def _agglomerative_cluster(self, objects: List[ClusterObject],
                               labels: List[DetectedLabel] = None) -> List[ObjectCluster]:
        """
        Perform agglomerative clustering with adaptive merge threshold.
        
        Args:
            objects: List of objects to cluster
            labels: List of labels to avoid subsuming during merges
        """
        if not objects:
            return []

        # Initialize: each object is its own cluster
        clusters = [
            ObjectCluster(cluster_id=i, objects=[obj])
            for i, obj in enumerate(objects)
        ]

        next_id = len(clusters)
        merge_history = []  # For debugging
        forbidden_pairs: Set[Tuple[int, int]] = set()  # Pairs that can't merge due to labels
        forbidden_count = 0

        while len(clusters) > 1:
            # Find closest pair of clusters that can merge
            best_dist = float('inf')
            best_pair = None

            for i, ca in enumerate(clusters):
                for j, cb in enumerate(clusters):
                    if i >= j:
                        continue
                    
                    # Skip pairs forbidden due to label subsumption
                    pair_key = (min(ca.cluster_id, cb.cluster_id), max(ca.cluster_id, cb.cluster_id))
                    if pair_key in forbidden_pairs:
                        continue
                    
                    dist = min_cluster_distance(ca, cb, self.vertical_weight)
                    if dist < best_dist:
                        best_dist = dist
                        best_pair = (i, j)

            if best_pair is None:
                break

            i, j = best_pair
            cluster_a = clusters[i]
            cluster_b = clusters[j]
            pair_key = (min(cluster_a.cluster_id, cluster_b.cluster_id),
                       max(cluster_a.cluster_id, cluster_b.cluster_id))

            # First: check label subsumption (can try other pairs if this fails)
            if labels and self.label_subsume_threshold < 1.0:
                if self._merge_would_subsume_label(cluster_a, cluster_b, labels):
                    forbidden_pairs.add(pair_key)
                    forbidden_count += 1
                    continue  # Try next closest pair

            # Second: check distance/density (break if this fails - no closer pair exists)
            if not self._should_merge(cluster_a, cluster_b, best_dist):
                break  # No more merges possible

            # Merge clusters
            new_cluster = ObjectCluster(
                cluster_id=next_id,
                objects=cluster_a.objects + cluster_b.objects
            )
            next_id += 1

            merge_history.append({
                'merged': (cluster_a.cluster_id, cluster_b.cluster_id),
                'distance': best_dist,
                'new_size': len(new_cluster.objects)
            })

            # Remove old clusters, add new one
            clusters = [c for idx, c in enumerate(clusters) if idx not in (i, j)]
            clusters.append(new_cluster)

        # Reassign sequential IDs
        for i, cluster in enumerate(clusters):
            cluster.cluster_id = i

        print(f"  Clustering: {len(objects)} objects -> {len(clusters)} clusters")
        print(f"  Merge operations: {len(merge_history)}")
        if forbidden_count > 0:
            print(f"  Forbidden merges (label subsumption): {forbidden_count}")
        if merge_history:
            distances = [m['distance'] for m in merge_history]
            print(f"  Merge distances: min={min(distances):.1f}, max={max(distances):.1f}, "
                  f"avg={sum(distances)/len(distances):.1f}")

        return clusters

    def _match_labels_to_clusters(self,
                                  clusters: List[ObjectCluster],
                                  labels: List[DetectedLabel]
                                  ) -> Tuple[List[ObjectCluster], List[DetectedLabel]]:
        """
        Match labels to nearest clusters using greedy assignment.
        
        Bigger clusters can have labels further away (relative to cluster size).

        Returns:
            Tuple of (clusters_with_labels, unmatched_labels)
        """
        if not clusters or not labels:
            return clusters, labels

        # Build distance matrix with size-relative thresholds
        distances = []
        for ci, cluster in enumerate(clusters):
            # Calculate cluster diagonal for size-relative distance
            bbox = cluster.bbox
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            diagonal = math.sqrt(width**2 + height**2)
            
            # Effective max distance: base + factor * cluster_diagonal
            effective_max_dist = (self.label_max_distance + 
                                  self.label_cluster_size_factor * diagonal)
            
            for li, label in enumerate(labels):
                dist = weighted_distance(cluster.center, label.center, self.vertical_weight)
                if dist <= effective_max_dist:
                    distances.append((dist, ci, li))

        # Sort by distance
        distances.sort(key=lambda x: x[0])

        # Greedy assignment
        used_clusters: Set[int] = set()
        used_labels: Set[int] = set()

        for dist, ci, li in distances:
            if ci in used_clusters or li in used_labels:
                continue
            clusters[ci].label = labels[li]
            used_clusters.add(ci)
            used_labels.add(li)

        unmatched_labels = [l for i, l in enumerate(labels) if i not in used_labels]

        labeled_count = sum(1 for c in clusters if c.label is not None)
        print(f"  Label matching: {labeled_count}/{len(clusters)} clusters labeled")
        print(f"  Unmatched labels: {len(unmatched_labels)}")
        if unmatched_labels:
            print(f"    Unmatched: {[l.text for l in unmatched_labels]}")

        return clusters, unmatched_labels

    def detect_clusters(self,
                        page: pymupdf.Page,
                        broken_connections: List[BrokenConnection],
                        structural_groups: List[StructuralGroup]
                        ) -> Tuple[List[ObjectCluster], List[DetectedLabel], List[FilteredGapFill],
                                   List[FilteredCirclePin], List[FilteredLineEnd]]:
        """
        Detect component clusters using density-aware agglomerative clustering.

        Returns:
            Tuple of (clusters, all_labels, gap_fills, circle_pins, line_ends)
        """
        # Step 1: Get labels
        labels = self.label_detector.detect_labels(page)
        print(f"Step 1: Found {len(labels)} labels")

        # Step 2: Get filtered objects using existing ComponentDetector logic
        base_detector = ComponentDetector(vertical_weight=self.vertical_weight)
        gap_fills, _, _ = base_detector._filter_gap_fills(broken_connections, structural_groups)
        circle_pins = base_detector._filter_circle_pins(structural_groups)
        line_ends = base_detector._filter_line_ends(structural_groups, broken_connections)

        print(f"Step 2: {len(gap_fills)} gaps, {len(circle_pins)} pins, {len(line_ends)} line ends")

        # Step 3: Convert to cluster objects
        objects = self._objects_from_filtered(gap_fills, circle_pins, line_ends)
        print(f"Step 3: {len(objects)} total objects to cluster")

        # Step 4: Agglomerative clustering (with label subsumption prevention)
        print("Step 4: Clustering...")
        clusters = self._agglomerative_cluster(objects, labels)

        # Step 5: Match labels to clusters
        print("Step 5: Matching labels...")
        clusters, unmatched_labels = self._match_labels_to_clusters(clusters, labels)

        # Summary
        print(f"\nCluster Summary:")
        print(f"  Total clusters: {len(clusters)}")
        print(f"  Labeled: {sum(1 for c in clusters if c.label)}")
        print(f"  Unlabeled: {sum(1 for c in clusters if not c.label)}")

        # Show cluster sizes
        sizes = sorted([len(c.objects) for c in clusters], reverse=True)
        print(f"  Cluster sizes: {sizes[:10]}{'...' if len(sizes) > 10 else ''}")

        return clusters, labels, gap_fills, circle_pins, line_ends


def visualize_clusters(
    page: pymupdf.Page,
    clusters: List[ObjectCluster],
    labels: List[DetectedLabel],
    gap_fills: List[FilteredGapFill],
    circle_pins: List[FilteredCirclePin],
    line_ends: List[FilteredLineEnd],
    output_path: str,
    scale: float = 2.0,
    structural_groups: List[StructuralGroup] = None
) -> str:
    """
    Visualize clustering results with labels associated by color.

    Shows:
    - Structural groups (light colored lines)
    - Individual objects (gaps, pins, line ends)
    - Cluster bounding boxes with color coding
    - Labels outside clusters, colored to match their associated cluster
    """
    # Render page as base
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img, 'RGBA')

    # Layer 1: Structural groups (colored wires)
    if structural_groups:
        for group in structural_groups:
            color_hex = group.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            for elem in group.elements:
                if elem.start_point and elem.end_point:
                    start = (elem.start_point.x * scale, elem.start_point.y * scale)
                    end = (elem.end_point.x * scale, elem.end_point.y * scale)
                    draw.line([start, end], fill=(r, g, b, 200), width=2)

    # Build map of label -> cluster color for associated labels
    label_to_color = {}
    assigned_labels = set()
    for cluster in clusters:
        if cluster.label:
            color_hex = cluster.primary_color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            label_to_color[id(cluster.label)] = (r, g, b)
            assigned_labels.add(id(cluster.label))

    # Layer 2: Draw cluster bounding boxes (without labels inside)
    for cluster in clusters:
        # Use cluster's primary color
        color_hex = cluster.primary_color.lstrip('#')
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
        
        # Get cluster bbox (objects only, not expanded to include label)
        x0, y0, x1, y1 = [c * scale for c in cluster.bbox]
        
        if cluster.label:
            # Labeled cluster: solid color fill and outline
            draw.rectangle([x0, y0, x1, y1],
                          fill=(r, g, b, 60),
                          outline=(r, g, b),
                          width=3)
        else:
            # Unlabeled cluster: lighter appearance
            draw.rectangle([x0, y0, x1, y1],
                          fill=(r, g, b, 30),
                          outline=(r, g, b, 150),
                          width=1)

    # Layer 3: Draw objects within clusters
    # Gap fills (rectangles)
    for gap in gap_fills:
        color_hex = gap.color.lstrip('#')
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
        sx, sy = gap.gap_start[0] * scale, gap.gap_start[1] * scale
        ex, ey = gap.gap_end[0] * scale, gap.gap_end[1] * scale
        dx, dy = ex - sx, ey - sy
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            thickness = 6.0
            nx, ny = -dy/length * thickness/2, dx/length * thickness/2
            points = [(sx + nx, sy + ny), (sx - nx, sy - ny), (ex - nx, ey - ny), (ex + nx, ey + ny)]
            draw.polygon(points, fill=(r, g, b, 200))

    # Circle pins
    for circ in circle_pins:
        color_hex = circ.color.lstrip('#')
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
        cx, cy = circ.center[0] * scale, circ.center[1] * scale
        radius = circ.radius * scale
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        draw.ellipse(bbox, outline=(r, g, b), width=3)

    # Line ends (diamonds)
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
        draw.polygon(diamond_points, fill=(r, g, b, 180), outline=(r, g, b))

    # Layer 4: Draw all labels with appropriate colors
    for label in labels:
        x0, y0, x1, y1 = [c * scale for c in label.bbox]
        
        if id(label) in assigned_labels:
            # Assigned label: use cluster's color
            r, g, b = label_to_color[id(label)]
            draw.rectangle([x0, y0, x1, y1],
                          fill=(r, g, b, 100),
                          outline=(r, g, b),
                          width=2)
            draw.text((x0 + 2, y0 + 2), label.text, fill=(r//2, g//2, b//2))
        else:
            # Unassigned label: orange/yellow
            draw.rectangle([x0, y0, x1, y1],
                          fill=(255, 200, 0, 100),
                          outline=(255, 140, 0),
                          width=2)
            draw.text((x0 + 2, y0 + 2), label.text, fill=(180, 100, 0))

    img.save(output_path)
    print(f"Saved: {output_path}")
    return output_path


def visualize_objects_only(
    page: pymupdf.Page,
    gap_fills: List[FilteredGapFill],
    circle_pins: List[FilteredCirclePin],
    line_ends: List[FilteredLineEnd],
    output_path: str,
    scale: float = 2.0,
    structural_groups: List[StructuralGroup] = None
) -> str:
    """
    Visualize just the objects without clustering - to see raw input.
    """
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img, 'RGBA')

    # Structural groups
    if structural_groups:
        for group in structural_groups:
            color_hex = group.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            for elem in group.elements:
                if elem.start_point and elem.end_point:
                    start = (elem.start_point.x * scale, elem.start_point.y * scale)
                    end = (elem.end_point.x * scale, elem.end_point.y * scale)
                    draw.line([start, end], fill=(r, g, b, 150), width=2)

    # Objects with bright markers
    for gap in gap_fills:
        cx, cy = gap.center[0] * scale, gap.center[1] * scale
        draw.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(255, 0, 0, 255), outline=(200, 0, 0))

    for circ in circle_pins:
        cx, cy = circ.center[0] * scale, circ.center[1] * scale
        draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=(0, 255, 0, 255), outline=(0, 200, 0))

    for end in line_ends:
        ex, ey = end.position[0] * scale, end.position[1] * scale
        draw.ellipse([ex-4, ey-4, ex+4, ey+4], fill=(0, 0, 255, 255), outline=(0, 0, 200))

    img.save(output_path)
    print(f"Saved: {output_path}")
    return output_path
