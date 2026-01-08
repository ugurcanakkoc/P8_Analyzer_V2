"""
Prepare Classification Dataset for YOLO Training

Takes the classified images and splits them into train/val/test sets
with the folder structure YOLO classification expects.

Usage:
    python prepare_classification_dataset.py --input ./classification_output/ornek_20260107_163847
"""

import os
import shutil
import random
import argparse
from pathlib import Path


def prepare_dataset(input_dir: str, output_dir: str = None,
                    train_ratio: float = 0.7, val_ratio: float = 0.15):
    """
    Split classified images into train/val/test sets.

    Args:
        input_dir: Directory with schematic/ and non_schematic/ folders
        output_dir: Output directory for dataset (default: YOLO/data/page_classifier)
        train_ratio: Fraction for training (default: 0.7)
        val_ratio: Fraction for validation (default: 0.15)
    """
    input_path = Path(input_dir)

    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path(__file__).parent.parent / "data" / "page_classifier"

    # Verify input structure
    schematic_dir = input_path / "schematic"
    non_schematic_dir = input_path / "non_schematic"

    if not schematic_dir.exists() or not non_schematic_dir.exists():
        print(f"[ERROR] Expected schematic/ and non_schematic/ folders in {input_path}")
        return

    # Get all images
    schematic_images = list(schematic_dir.glob("*.png"))
    non_schematic_images = list(non_schematic_dir.glob("*.png"))

    print(f"[INFO] Found {len(schematic_images)} schematic images")
    print(f"[INFO] Found {len(non_schematic_images)} non-schematic images")

    # Shuffle for random split
    random.seed(42)  # Reproducible
    random.shuffle(schematic_images)
    random.shuffle(non_schematic_images)

    # Calculate split indices
    def split_list(images, train_r, val_r):
        n = len(images)
        train_end = int(n * train_r)
        val_end = train_end + int(n * val_r)
        return images[:train_end], images[train_end:val_end], images[val_end:]

    s_train, s_val, s_test = split_list(schematic_images, train_ratio, val_ratio)
    n_train, n_val, n_test = split_list(non_schematic_images, train_ratio, val_ratio)

    print(f"\n[INFO] Split (schematic): train={len(s_train)}, val={len(s_val)}, test={len(s_test)}")
    print(f"[INFO] Split (non_schematic): train={len(n_train)}, val={len(n_val)}, test={len(n_test)}")

    # Create output structure
    # YOLO classification expects: dataset/train/class_name/*.jpg
    splits = {
        "train": (s_train, n_train),
        "val": (s_val, n_val),
        "test": (s_test, n_test)
    }

    for split_name, (schematic_list, non_schematic_list) in splits.items():
        # Create directories
        schematic_out = output_path / split_name / "schematic"
        non_schematic_out = output_path / split_name / "non_schematic"
        schematic_out.mkdir(parents=True, exist_ok=True)
        non_schematic_out.mkdir(parents=True, exist_ok=True)

        # Copy images
        for img in schematic_list:
            shutil.copy(img, schematic_out / img.name)
        for img in non_schematic_list:
            shutil.copy(img, non_schematic_out / img.name)

    # Create dataset.yaml for YOLO
    yaml_content = f"""# Page Classification Dataset
# Auto-generated from classified PDF pages

path: {output_path.absolute()}
train: train
val: val
test: test

# Classes
names:
  0: schematic
  1: non_schematic

# Dataset statistics
# Total: {len(schematic_images) + len(non_schematic_images)} images
# Schematic: {len(schematic_images)}
# Non-schematic: {len(non_schematic_images)}
"""

    yaml_path = output_path / "dataset.yaml"
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"\n[SUCCESS] Dataset prepared at: {output_path}")
    print(f"[INFO] Dataset config: {yaml_path}")
    print(f"\n[INFO] Total images:")
    print(f"  Train: {len(s_train) + len(n_train)}")
    print(f"  Val: {len(s_val) + len(n_val)}")
    print(f"  Test: {len(s_test) + len(n_test)}")


def main():
    parser = argparse.ArgumentParser(description="Prepare YOLO classification dataset")
    parser.add_argument("--input", "-i", required=True,
                        help="Input directory with schematic/ and non_schematic/ folders")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: YOLO/data/page_classifier)")
    parser.add_argument("--train-ratio", type=float, default=0.7,
                        help="Training set ratio (default: 0.7)")
    parser.add_argument("--val-ratio", type=float, default=0.15,
                        help="Validation set ratio (default: 0.15)")

    args = parser.parse_args()
    prepare_dataset(args.input, args.output, args.train_ratio, args.val_ratio)


if __name__ == "__main__":
    main()
