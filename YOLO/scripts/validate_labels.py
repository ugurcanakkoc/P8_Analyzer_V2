"""
YOLO Label Validation Script
=============================

Validates YOLO training data for quality and consistency.
Supports both standard YOLO format (5 values) and OBB format (9 values).

Features:
- Verifies label-image file matching
- Validates coordinate ranges [0, 1]
- Checks class IDs against classes.txt
- Reports class distribution statistics
- Optionally visualizes samples with annotations
- Auto-fix common issues (optional)

Usage:
    python validate_labels.py [--data-dir ../data] [--fix] [--visualize 5]
"""

import argparse
import os
import sys
import random
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class LabelValidator:
    """Validates YOLO training labels for quality and consistency."""

    # Label formats
    FORMAT_STANDARD = "standard"  # class_id cx cy w h (5 values)
    FORMAT_OBB = "obb"            # class_id x1 y1 x2 y2 x3 y3 x4 y4 (9 values)

    def __init__(self, data_dir: Path, classes_file: Optional[Path] = None):
        """
        Initialize validator.

        Args:
            data_dir: Path to data directory (contains images/ and labels/)
            classes_file: Path to classes.txt (default: data_dir/classes.txt)
        """
        self.data_dir = Path(data_dir)
        self.classes_file = classes_file or (self.data_dir / "classes.txt")

        self.classes: List[str] = []
        self.issues: List[Dict] = []
        self.stats = {
            "total_images": 0,
            "total_labels": 0,
            "total_boxes": 0,
            "format": None,
            "class_distribution": defaultdict(int),
            "boxes_per_image": [],
            "orphan_images": [],
            "orphan_labels": [],
            "empty_labels": [],
            "invalid_format": [],
            "out_of_range": [],
            "invalid_class_id": [],
        }

        self._load_classes()

    def _load_classes(self):
        """Load class names from classes.txt."""
        if self.classes_file.exists():
            with open(self.classes_file, 'r', encoding='utf-8') as f:
                self.classes = [line.strip() for line in f if line.strip()]
            print(f"[INFO] Loaded {len(self.classes)} classes from {self.classes_file}")
        else:
            print(f"[WARNING] Classes file not found: {self.classes_file}")
            print("         Class ID validation will be skipped.")

    def validate_split(self, split: str = "train") -> Dict:
        """
        Validate a data split (train/val/test).

        Args:
            split: Name of the split to validate

        Returns:
            Dictionary with validation results
        """
        images_dir = self.data_dir / "images" / split
        labels_dir = self.data_dir / "labels" / split

        print(f"\n{'='*60}")
        print(f"  Validating: {split}")
        print(f"{'='*60}")
        print(f"  Images: {images_dir}")
        print(f"  Labels: {labels_dir}")

        if not images_dir.exists():
            print(f"[ERROR] Images directory not found: {images_dir}")
            return self.stats

        if not labels_dir.exists():
            print(f"[ERROR] Labels directory not found: {labels_dir}")
            return self.stats

        # Get image and label files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}
        image_files = {
            f.stem: f for f in images_dir.iterdir()
            if f.suffix.lower() in image_extensions
        }
        label_files = {
            f.stem: f for f in labels_dir.iterdir()
            if f.suffix == '.txt'
        }

        self.stats["total_images"] = len(image_files)
        self.stats["total_labels"] = len(label_files)

        print(f"\n[FILES]")
        print(f"  Images: {len(image_files)}")
        print(f"  Labels: {len(label_files)}")

        # Check for orphans
        self.stats["orphan_images"] = [
            str(image_files[name]) for name in image_files
            if name not in label_files
        ]
        self.stats["orphan_labels"] = [
            str(label_files[name]) for name in label_files
            if name not in image_files
        ]

        if self.stats["orphan_images"]:
            print(f"\n[WARNING] {len(self.stats['orphan_images'])} images without labels:")
            for f in self.stats["orphan_images"][:5]:
                print(f"  - {Path(f).name}")
            if len(self.stats["orphan_images"]) > 5:
                print(f"  ... and {len(self.stats['orphan_images']) - 5} more")

        if self.stats["orphan_labels"]:
            print(f"\n[WARNING] {len(self.stats['orphan_labels'])} labels without images:")
            for f in self.stats["orphan_labels"][:5]:
                print(f"  - {Path(f).name}")
            if len(self.stats["orphan_labels"]) > 5:
                print(f"  ... and {len(self.stats['orphan_labels']) - 5} more")

        # Validate each label file
        print(f"\n[VALIDATING LABELS]")
        for name, label_path in label_files.items():
            if name not in image_files:
                continue  # Skip orphan labels

            self._validate_label_file(label_path)

        # Determine format
        if self.stats["total_boxes"] > 0:
            print(f"\n[FORMAT]")
            print(f"  Detected format: {self.stats['format']}")

        return self.stats

    def _validate_label_file(self, label_path: Path):
        """Validate a single label file."""
        try:
            with open(label_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.stats["invalid_format"].append({
                "file": str(label_path),
                "error": f"Cannot read file: {e}"
            })
            return

        if not lines or all(not line.strip() for line in lines):
            self.stats["empty_labels"].append(str(label_path))
            self.stats["boxes_per_image"].append(0)
            return

        box_count = 0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split()

            # Determine format
            if len(parts) == 5:
                detected_format = self.FORMAT_STANDARD
            elif len(parts) == 9:
                detected_format = self.FORMAT_OBB
            else:
                self.stats["invalid_format"].append({
                    "file": str(label_path),
                    "line": line_num,
                    "error": f"Invalid number of values: {len(parts)} (expected 5 or 9)",
                    "content": line[:50]
                })
                continue

            # Set or check format consistency
            if self.stats["format"] is None:
                self.stats["format"] = detected_format
            elif self.stats["format"] != detected_format:
                self.stats["invalid_format"].append({
                    "file": str(label_path),
                    "line": line_num,
                    "error": f"Mixed formats: expected {self.stats['format']}, got {detected_format}",
                    "content": line[:50]
                })

            # Parse values
            try:
                values = [float(v) for v in parts]
            except ValueError as e:
                self.stats["invalid_format"].append({
                    "file": str(label_path),
                    "line": line_num,
                    "error": f"Cannot parse values: {e}",
                    "content": line[:50]
                })
                continue

            # Validate class ID
            class_id = int(values[0])
            if self.classes and (class_id < 0 or class_id >= len(self.classes)):
                self.stats["invalid_class_id"].append({
                    "file": str(label_path),
                    "line": line_num,
                    "class_id": class_id,
                    "max_valid": len(self.classes) - 1
                })
            else:
                if self.classes:
                    class_name = self.classes[class_id]
                else:
                    class_name = f"class_{class_id}"
                self.stats["class_distribution"][class_name] += 1

            # Validate coordinates are in [0, 1]
            coords = values[1:]
            out_of_range = [
                (i, v) for i, v in enumerate(coords)
                if v < 0.0 or v > 1.0
            ]
            if out_of_range:
                self.stats["out_of_range"].append({
                    "file": str(label_path),
                    "line": line_num,
                    "issues": [(i, v) for i, v in out_of_range]
                })

            box_count += 1
            self.stats["total_boxes"] += 1

        self.stats["boxes_per_image"].append(box_count)

    def print_report(self):
        """Print validation report."""
        print(f"\n{'='*60}")
        print("  VALIDATION REPORT")
        print(f"{'='*60}")

        # Summary
        print(f"\n[SUMMARY]")
        print(f"  Total images: {self.stats['total_images']}")
        print(f"  Total labels: {self.stats['total_labels']}")
        print(f"  Total boxes: {self.stats['total_boxes']}")
        print(f"  Label format: {self.stats['format'] or 'Unknown'}")

        if self.stats["boxes_per_image"]:
            avg_boxes = sum(self.stats["boxes_per_image"]) / len(self.stats["boxes_per_image"])
            max_boxes = max(self.stats["boxes_per_image"])
            min_boxes = min(self.stats["boxes_per_image"])
            print(f"  Boxes per image: min={min_boxes}, avg={avg_boxes:.1f}, max={max_boxes}")

        # Class distribution
        if self.stats["class_distribution"]:
            print(f"\n[CLASS DISTRIBUTION]")
            total = sum(self.stats["class_distribution"].values())
            for class_name, count in sorted(self.stats["class_distribution"].items(),
                                            key=lambda x: x[1], reverse=True):
                pct = (count / total * 100) if total > 0 else 0
                bar_len = int(pct / 2)
                bar = '#' * bar_len
                print(f"  {class_name:20s} {count:5d} ({pct:5.1f}%) {bar}")

        # Issues
        issue_count = (
            len(self.stats["orphan_images"]) +
            len(self.stats["orphan_labels"]) +
            len(self.stats["empty_labels"]) +
            len(self.stats["invalid_format"]) +
            len(self.stats["out_of_range"]) +
            len(self.stats["invalid_class_id"])
        )

        print(f"\n[ISSUES] Total: {issue_count}")

        if self.stats["orphan_images"]:
            print(f"  - Images without labels: {len(self.stats['orphan_images'])}")

        if self.stats["orphan_labels"]:
            print(f"  - Labels without images: {len(self.stats['orphan_labels'])}")

        if self.stats["empty_labels"]:
            print(f"  - Empty label files: {len(self.stats['empty_labels'])}")

        if self.stats["invalid_format"]:
            print(f"  - Invalid format errors: {len(self.stats['invalid_format'])}")
            for issue in self.stats["invalid_format"][:3]:
                print(f"    * {Path(issue['file']).name}:{issue.get('line', '?')}: {issue['error']}")
            if len(self.stats["invalid_format"]) > 3:
                print(f"    ... and {len(self.stats['invalid_format']) - 3} more")

        if self.stats["out_of_range"]:
            print(f"  - Coordinates out of [0,1] range: {len(self.stats['out_of_range'])}")

        if self.stats["invalid_class_id"]:
            print(f"  - Invalid class IDs: {len(self.stats['invalid_class_id'])}")

        # Overall status
        print(f"\n{'='*60}")
        if issue_count == 0:
            print("  STATUS: ALL CHECKS PASSED")
        else:
            print(f"  STATUS: {issue_count} ISSUES FOUND - Review and fix before training")
        print(f"{'='*60}")

        return issue_count == 0

    def visualize_samples(self, split: str = "train", num_samples: int = 5, output_dir: Optional[Path] = None):
        """
        Visualize random samples with annotations.

        Args:
            split: Data split to sample from
            num_samples: Number of samples to visualize
            output_dir: Directory to save visualizations (default: YOLO/visualizations/)
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            print("[ERROR] Pillow required for visualization. Install with: pip install Pillow")
            return

        images_dir = self.data_dir / "images" / split
        labels_dir = self.data_dir / "labels" / split
        output_dir = output_dir or (self.data_dir.parent / "visualizations")
        output_dir.mkdir(exist_ok=True)

        # Get paired files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        pairs = []
        for img_path in images_dir.iterdir():
            if img_path.suffix.lower() not in image_extensions:
                continue
            label_path = labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                pairs.append((img_path, label_path))

        if not pairs:
            print("[WARNING] No image-label pairs found for visualization")
            return

        # Sample
        samples = random.sample(pairs, min(num_samples, len(pairs)))

        # Colors for classes
        colors = [
            "#FF0000", "#00FF00", "#0000FF", "#FFFF00",
            "#FF00FF", "#00FFFF", "#FFA500", "#800080",
            "#008000", "#000080"
        ]

        print(f"\n[VISUALIZATION] Generating {len(samples)} samples...")

        for img_path, label_path in samples:
            try:
                img = Image.open(img_path).convert("RGB")
                draw = ImageDraw.Draw(img)
                img_w, img_h = img.size

                with open(label_path, 'r') as f:
                    lines = f.readlines()

                for line in lines:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue

                    class_id = int(float(parts[0]))
                    color = colors[class_id % len(colors)]

                    if len(parts) == 5:
                        # Standard format: cx cy w h
                        cx, cy, w, h = map(float, parts[1:5])
                        x1 = (cx - w/2) * img_w
                        y1 = (cy - h/2) * img_h
                        x2 = (cx + w/2) * img_w
                        y2 = (cy + h/2) * img_h
                        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

                    elif len(parts) == 9:
                        # OBB format: x1 y1 x2 y2 x3 y3 x4 y4
                        coords = list(map(float, parts[1:9]))
                        points = [
                            (coords[0] * img_w, coords[1] * img_h),
                            (coords[2] * img_w, coords[3] * img_h),
                            (coords[4] * img_w, coords[5] * img_h),
                            (coords[6] * img_w, coords[7] * img_h),
                        ]
                        draw.polygon(points, outline=color, width=2)

                    # Draw class label
                    class_name = self.classes[class_id] if class_id < len(self.classes) else f"cls_{class_id}"
                    if len(parts) == 5:
                        label_pos = (x1, y1 - 15)
                    else:
                        label_pos = (points[0][0], points[0][1] - 15)
                    draw.text(label_pos, class_name, fill=color)

                # Save
                out_path = output_dir / f"viz_{img_path.name}"
                img.save(out_path)
                print(f"  Saved: {out_path.name}")

            except Exception as e:
                print(f"  [ERROR] {img_path.name}: {e}")

        print(f"\nVisualizations saved to: {output_dir}")

    def auto_fix(self, dry_run: bool = True):
        """
        Attempt to auto-fix common issues.

        Args:
            dry_run: If True, only report what would be fixed
        """
        print(f"\n[AUTO-FIX] {'DRY RUN - ' if dry_run else ''}Attempting fixes...")

        fixes = 0

        # Fix out-of-range coordinates by clamping
        for issue in self.stats["out_of_range"]:
            label_path = Path(issue["file"])
            if not dry_run:
                try:
                    with open(label_path, 'r') as f:
                        lines = f.readlines()

                    fixed_lines = []
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            class_id = parts[0]
                            coords = [max(0.0, min(1.0, float(v))) for v in parts[1:]]
                            fixed_line = f"{class_id} " + " ".join(f"{c:.6f}" for c in coords)
                            fixed_lines.append(fixed_line)
                        else:
                            fixed_lines.append(line.strip())

                    with open(label_path, 'w') as f:
                        f.write("\n".join(fixed_lines) + "\n")

                    fixes += 1
                except Exception as e:
                    print(f"  [ERROR] Could not fix {label_path.name}: {e}")
            else:
                print(f"  Would fix: {label_path.name} (clamp coordinates)")
                fixes += 1

        # Remove orphan labels
        for label_path in self.stats["orphan_labels"]:
            if not dry_run:
                try:
                    Path(label_path).unlink()
                    fixes += 1
                except Exception as e:
                    print(f"  [ERROR] Could not remove {label_path}: {e}")
            else:
                print(f"  Would remove: {Path(label_path).name} (orphan label)")
                fixes += 1

        print(f"\n  {'Would fix' if dry_run else 'Fixed'}: {fixes} issues")
        if dry_run and fixes > 0:
            print("  Run with --fix to apply changes")


def main():
    parser = argparse.ArgumentParser(description="Validate YOLO training labels")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Path to data directory (default: YOLO/data)")
    parser.add_argument("--split", type=str, default="train",
                        help="Data split to validate (train/val/test)")
    parser.add_argument("--all-splits", action="store_true",
                        help="Validate all splits")
    parser.add_argument("--visualize", type=int, default=0,
                        help="Number of samples to visualize")
    parser.add_argument("--fix", action="store_true",
                        help="Attempt to auto-fix issues")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what --fix would do without making changes")

    args = parser.parse_args()

    # Determine data directory
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        script_dir = Path(__file__).parent
        data_dir = script_dir.parent / "data"

    print(f"[INFO] Data directory: {data_dir}")

    # Create validator
    validator = LabelValidator(data_dir)

    # Validate splits
    if args.all_splits:
        splits = ["train", "val", "test"]
    else:
        splits = [args.split]

    all_passed = True
    for split in splits:
        split_dir = data_dir / "images" / split
        if split_dir.exists():
            validator.validate_split(split)
        else:
            print(f"\n[SKIP] Split '{split}' not found: {split_dir}")

    # Print report
    passed = validator.print_report()
    all_passed = all_passed and passed

    # Visualize if requested
    if args.visualize > 0:
        validator.visualize_samples(args.split, args.visualize)

    # Auto-fix if requested
    if args.fix or args.dry_run:
        validator.auto_fix(dry_run=args.dry_run or not args.fix)

    # Exit code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
