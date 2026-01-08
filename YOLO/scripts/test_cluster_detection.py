#!/usr/bin/env python
"""
Test clustering-based component detection.

Compares the new clustering approach with the existing label-first approach.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf
from p8_analyzer.core.analyzer import analyze_page_vectors
from p8_analyzer.core.models import AnalysisConfig
from p8_analyzer.detection.cluster_detector import (
    ClusterDetector,
    visualize_clusters,
    visualize_objects_only
)


def run_cluster_detection(pdf_path: str, page_num: int, output_dir: str,
                          absolute_min_gap: float = 15.0,
                          density_factor: float = 2.0,
                          max_gap: float = 80.0,
                          vertical_weight: float = 3.0,
                          label_max_distance: float = 60.0):
    """Run clustering-based component detection."""
    print(f"\n{'='*60}")
    print(f"Cluster-Based Component Detection")
    print(f"{'='*60}")
    print(f"PDF: {pdf_path}")
    print(f"Page: {page_num}")
    print(f"Parameters:")
    print(f"  absolute_min_gap: {absolute_min_gap}")
    print(f"  density_factor: {density_factor}")
    print(f"  max_gap: {max_gap}")
    print(f"  vertical_weight: {vertical_weight}")
    print(f"  label_max_distance: {label_max_distance}")
    print(f"{'='*60}\n")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Open PDF
    doc = pymupdf.open(pdf_path)
    page = doc.load_page(page_num - 1)
    drawings = page.get_drawings()

    print(f"Page size: {page.rect.width:.1f} x {page.rect.height:.1f}")
    print(f"Drawings: {len(drawings)}")

    # Run full analysis pipeline
    print("\nRunning full circuit analysis...")
    config = AnalysisConfig()
    result = analyze_page_vectors(drawings, page.rect, page_num, config)

    print(f"  Structural groups: {len(result.structural_groups)}")
    print(f"  Broken connections: {len(result.broken_connections)}")

    # Run cluster detection
    print("\n" + "="*60)
    print("Running cluster detection...")
    print("="*60)

    detector = ClusterDetector(
        vertical_weight=vertical_weight,
        absolute_min_gap=absolute_min_gap,
        density_factor=density_factor,
        max_gap=max_gap,
        label_max_distance=label_max_distance
    )

    clusters, labels, gap_fills, circle_pins, line_ends = detector.detect_clusters(
        page,
        result.broken_connections,
        result.structural_groups
    )

    # Create visualizations
    print("\nCreating visualizations...")

    # 1. Objects only (input to clustering)
    objects_path = str(output_path / f"page{page_num}_1_objects.png")
    visualize_objects_only(
        page, gap_fills, circle_pins, line_ends, objects_path, scale=2.0,
        structural_groups=result.structural_groups
    )

    # 2. Clustering result
    clusters_path = str(output_path / f"page{page_num}_2_clusters.png")
    visualize_clusters(
        page, clusters, labels, gap_fills, circle_pins, line_ends,
        clusters_path, scale=2.0,
        structural_groups=result.structural_groups
    )

    doc.close()

    # Detailed summary
    print(f"\n{'='*60}")
    print("CLUSTERING SUMMARY")
    print(f"{'='*60}")
    print(f"Input objects: {len(gap_fills)} gaps + {len(circle_pins)} pins + {len(line_ends)} ends = {len(gap_fills)+len(circle_pins)+len(line_ends)}")
    print(f"Labels found: {len(labels)}")
    print(f"Clusters formed: {len(clusters)}")
    print(f"  - Labeled clusters: {sum(1 for c in clusters if c.label)}")
    print(f"  - Unlabeled clusters: {sum(1 for c in clusters if not c.label)}")

    # Cluster details with positions
    print("\nCluster Details (sorted by size):")
    print(f"{'ID':>4} {'Objs':>5} {'X':>6} {'Y':>6} {'W':>5} {'H':>5} {'Label':<12} Composition")
    print("-" * 75)
    for cluster in sorted(clusters, key=lambda c: len(c.objects), reverse=True):
        label_str = cluster.label.text if cluster.label else "-"
        obj_types = {}
        for obj in cluster.objects:
            obj_types[obj.obj_type] = obj_types.get(obj.obj_type, 0) + 1
        type_str = ", ".join(f"{v}{k[0]}" for k, v in obj_types.items())
        bbox = cluster.bbox
        x, y = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        print(f"C{cluster.cluster_id:>3} {len(cluster.objects):>5} {x:>6.0f} {y:>6.0f} {w:>5.0f} {h:>5.0f} {label_str:<12} {type_str}")

    print(f"\nOutput: {output_dir}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="?", default="data/ornek.pdf")
    parser.add_argument("-p", "--page", type=int, default=11)
    parser.add_argument("-o", "--output", default="YOLO/visualizations/cluster_detection")
    parser.add_argument("--min-gap", type=float, default=15.0)
    parser.add_argument("--density-factor", type=float, default=2.0)
    parser.add_argument("--max-gap", type=float, default=80.0)
    parser.add_argument("--vertical-weight", type=float, default=3.0)
    parser.add_argument("--label-dist", type=float, default=60.0)
    args = parser.parse_args()

    run_cluster_detection(
        args.pdf, args.page, args.output,
        absolute_min_gap=args.min_gap,
        density_factor=args.density_factor,
        max_gap=args.max_gap,
        vertical_weight=args.vertical_weight,
        label_max_distance=args.label_dist
    )


if __name__ == "__main__":
    main()
