#!/usr/bin/env python
"""
Test component detection using the full circuit analysis pipeline.

Uses the same filtering logic as UVP svg_export:
- Only broken_connections where path1_index belongs to a structural group
- Only circles that belong to structural groups
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf
from p8_analyzer.core.analyzer import analyze_page_vectors
from p8_analyzer.core.models import AnalysisConfig
from p8_analyzer.detection import (
    ComponentDetector,
    visualize_component_detection,
    create_step_visualization
)


def run_detection(pdf_path: str, page_num: int, output_dir: str,
                  max_h_dist: float = 100.0,
                  max_v_dist: float = 40.0,
                  vertical_weight: float = 3.0):
    """Run component detection with full circuit analysis pipeline."""
    print(f"\n{'='*60}")
    print(f"Component Detection Test (UVP-filtered)")
    print(f"{'='*60}")
    print(f"PDF: {pdf_path}")
    print(f"Page: {page_num}")
    print(f"max_horizontal_distance: {max_h_dist}")
    print(f"max_vertical_distance: {max_v_dist}")
    print(f"vertical_weight: {vertical_weight}")
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
    print(f"  Raw broken_connections: {len(result.broken_connections)}")
    print(f"  All circles: {len(result.all_circles)}")

    # Count circles in structural groups
    circles_in_groups = sum(len(g.circles) for g in result.structural_groups)
    print(f"  Circles in structural groups: {circles_in_groups}")

    # Run component detection with UVP filtering
    print("\nRunning component detection (UVP-filtered)...")
    detector = ComponentDetector(
        max_horizontal_distance=max_h_dist,
        max_vertical_distance=max_v_dist,
        vertical_weight=vertical_weight
    )

    # Pass broken_connections and structural_groups (NEW API)
    components, labels, gap_fills, circle_pins, line_ends = detector.detect_components(
        page,
        result.broken_connections,
        result.structural_groups
    )

    # Create visualizations with full circuit pipeline
    print("\nCreating visualizations...")

    # Step-by-step visualization
    step_dir = str(output_path / f"page{page_num}_steps")
    create_step_visualization(
        page, labels, gap_fills, components, step_dir, scale=2.0,
        structural_groups=result.structural_groups,
        circle_pins=circle_pins,
        line_ends=line_ends
    )

    # Combined visualization with all layers
    combined_path = str(output_path / f"page{page_num}_combined.png")
    visualize_component_detection(
        page, labels, gap_fills, components, combined_path, scale=2.0,
        structural_groups=result.structural_groups,
        circle_pins=circle_pins,
        line_ends=line_ends
    )

    # Components only (without unassigned labels)
    components_only = str(output_path / f"page{page_num}_components_only.png")
    visualize_component_detection(
        page, labels, gap_fills, components, components_only, scale=2.0,
        show_all=False,
        structural_groups=result.structural_groups,
        circle_pins=circle_pins,
        line_ends=line_ends
    )

    doc.close()

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Labels detected: {len(labels)}")
    print(f"Filtered gap fills: {len(gap_fills)} (from {len(result.broken_connections)} raw)")
    print(f"Filtered circle pins: {len(circle_pins)} (from {len(result.all_circles)} total)")
    print(f"Terminal line ends: {len(line_ends)}")
    print(f"Components: {len(components)}")
    print(f"  - With elements: {sum(1 for c in components if c.element_count > 0)}")

    if components:
        print("\nTop components:")
        for c in components[:10]:
            print(f"  {c.name}: {len(c.gap_fills)} gaps, {len(c.circle_pins)} pins, {len(c.line_ends)} ends, conf={c.confidence:.2f}")

    print(f"\nOutput: {output_dir}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="?", default="data/ornek.pdf")
    parser.add_argument("-p", "--page", type=int, default=11)
    parser.add_argument("-o", "--output", default="YOLO/visualizations/component_detection")
    parser.add_argument("--max-h-dist", type=float, default=100.0)
    parser.add_argument("--max-v-dist", type=float, default=40.0)
    parser.add_argument("--vertical-weight", type=float, default=3.0)
    args = parser.parse_args()

    run_detection(args.pdf, args.page, args.output,
                  args.max_h_dist, args.max_v_dist, args.vertical_weight)


if __name__ == "__main__":
    main()
