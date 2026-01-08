#!/usr/bin/env python
"""
Generate YOLO training dataset for component label detection.

This script:
1. Uses the page classifier to find schematic pages
2. Extracts labels using regex-based detection
3. Exports images and YOLO format labels for training
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
import pymupdf

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from p8_analyzer.detection import LabelDetector, export_labels_to_yolo


def generate_dataset(
    pdf_path: str,
    output_dir: str,
    page_numbers: list = None,
    image_scale: float = 2.0,
    class_name: str = "Label"
):
    """
    Generate YOLO dataset from PDF.

    Args:
        pdf_path: Path to PDF file
        output_dir: Output directory for dataset
        page_numbers: Specific pages to process (1-indexed), or None for all
        image_scale: Scale factor for images
        class_name: Class name for the labels
    """
    output_path = Path(output_dir)

    # Create directory structure
    images_dir = output_path / "images" / "train"
    labels_dir = output_path / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Create detector
    detector = LabelDetector()

    # Open PDF
    doc = pymupdf.open(pdf_path)
    pdf_name = Path(pdf_path).stem

    if page_numbers is None:
        page_numbers = list(range(1, doc.page_count + 1))

    print(f"Processing {len(page_numbers)} pages from {pdf_path}")
    print(f"Output directory: {output_path}")
    print("=" * 60)

    total_labels = 0
    pages_with_labels = 0

    for page_num in page_numbers:
        page = doc.load_page(page_num - 1)

        # Detect labels
        labels = detector.detect_labels(page)

        if not labels:
            print(f"  Page {page_num}: No labels found, skipping")
            continue

        # Generate filenames
        base_name = f"{pdf_name}_page{page_num:04d}"
        image_file = images_dir / f"{base_name}.png"
        label_file = labels_dir / f"{base_name}.txt"

        # Render page to image
        mat = pymupdf.Matrix(image_scale, image_scale)
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(image_file))

        # Export labels in YOLO format
        export_labels_to_yolo(
            labels,
            page.rect.width,
            page.rect.height,
            str(label_file)
        )

        total_labels += len(labels)
        pages_with_labels += 1

        print(f"  Page {page_num}: {len(labels)} labels -> {image_file.name}")

    doc.close()

    # Create data.yaml for YOLO
    yaml_content = f"""# Label Detection Dataset
# Generated: {datetime.now().isoformat()}
# Source: {pdf_path}

path: {output_path.absolute()}
train: images/train
val: images/train

nc: 1
names:
  0: {class_name}
"""
    yaml_file = output_path / "data.yaml"
    yaml_file.write_text(yaml_content)

    print("=" * 60)
    print(f"Dataset generation complete!")
    print(f"  Pages processed: {pages_with_labels}")
    print(f"  Total labels: {total_labels}")
    print(f"  Output: {output_path}")
    print(f"  Config: {yaml_file}")

    return {
        "pages_processed": pages_with_labels,
        "total_labels": total_labels,
        "output_dir": str(output_path),
        "yaml_file": str(yaml_file)
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate YOLO dataset for label detection")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("-o", "--output", default="YOLO/data/labels_dataset",
                       help="Output directory")
    parser.add_argument("-p", "--pages", type=str, default=None,
                       help="Page numbers (comma-separated, e.g., '1,5,10-15')")
    parser.add_argument("-s", "--scale", type=float, default=2.0,
                       help="Image scale factor")

    args = parser.parse_args()

    # Parse page numbers
    page_numbers = None
    if args.pages:
        page_numbers = []
        for part in args.pages.split(','):
            if '-' in part:
                start, end = part.split('-')
                page_numbers.extend(range(int(start), int(end) + 1))
            else:
                page_numbers.append(int(part))

    generate_dataset(
        pdf_path=args.pdf_path,
        output_dir=args.output,
        page_numbers=page_numbers,
        image_scale=args.scale
    )


if __name__ == "__main__":
    main()
