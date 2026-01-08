#!/usr/bin/env python
"""
Split YOLO dataset into train and validation sets.
"""

import os
import random
import shutil
from pathlib import Path


def split_dataset(dataset_dir: str, val_ratio: float = 0.2, seed: int = 42):
    """
    Split dataset into train and validation sets.

    Args:
        dataset_dir: Path to dataset directory
        val_ratio: Ratio of validation data (0-1)
        seed: Random seed for reproducibility
    """
    dataset_path = Path(dataset_dir)
    images_train = dataset_path / "images" / "train"
    labels_train = dataset_path / "labels" / "train"

    # Create val directories
    images_val = dataset_path / "images" / "val"
    labels_val = dataset_path / "labels" / "val"
    images_val.mkdir(parents=True, exist_ok=True)
    labels_val.mkdir(parents=True, exist_ok=True)

    # Get all image files
    image_files = list(images_train.glob("*.png"))
    random.seed(seed)
    random.shuffle(image_files)

    # Calculate split
    val_count = int(len(image_files) * val_ratio)
    val_files = image_files[:val_count]

    print(f"Total images: {len(image_files)}")
    print(f"Validation set: {val_count} ({val_ratio*100:.0f}%)")
    print(f"Training set: {len(image_files) - val_count}")

    # Move validation files
    for img_file in val_files:
        # Move image
        shutil.move(str(img_file), str(images_val / img_file.name))

        # Move label
        label_file = labels_train / (img_file.stem + ".txt")
        if label_file.exists():
            shutil.move(str(label_file), str(labels_val / label_file.name))

    # Update data.yaml
    yaml_file = dataset_path / "data.yaml"
    yaml_content = f"""# Label Detection Dataset (Split)
path: {dataset_path.absolute()}
train: images/train
val: images/val

nc: 1
names:
  0: Label
"""
    yaml_file.write_text(yaml_content)

    print(f"Updated: {yaml_file}")
    print("Done!")


if __name__ == "__main__":
    import sys
    dataset_dir = sys.argv[1] if len(sys.argv) > 1 else "YOLO/data/labels_dataset"
    val_ratio = float(sys.argv[2]) if len(sys.argv) > 2 else 0.2
    split_dataset(dataset_dir, val_ratio)
