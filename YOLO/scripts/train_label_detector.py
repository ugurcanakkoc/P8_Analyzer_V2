#!/usr/bin/env python
"""
Train YOLOv8 model for component label detection.

This trains a detection model to find P8 component labels (-X1, -1G35, etc.)
in electrical schematic images.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def train_label_detector(
    data_yaml: str = "YOLO/data/labels_dataset/data.yaml",
    epochs: int = 50,
    imgsz: int = 640,
    batch: int = 8,
    model_base: str = "yolov8n.pt",
    project: str = "YOLO/runs/label_detection",
    name: str = None
):
    """
    Train YOLOv8 model for label detection.

    Args:
        data_yaml: Path to data.yaml config
        epochs: Number of training epochs
        imgsz: Image size
        batch: Batch size
        model_base: Base model to finetune
        project: Output project directory
        name: Experiment name
    """
    from ultralytics import YOLO

    # Generate name if not provided
    if name is None:
        name = f"labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print("=" * 60)
    print("YOLO Label Detector Training")
    print("=" * 60)
    print(f"Data: {data_yaml}")
    print(f"Base model: {model_base}")
    print(f"Epochs: {epochs}")
    print(f"Image size: {imgsz}")
    print(f"Batch size: {batch}")
    print(f"Output: {project}/{name}")
    print("=" * 60)

    # Load model
    model = YOLO(model_base)

    # Train (workers=2 to avoid Windows paging file issues)
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=project,
        name=name,
        patience=10,
        save=True,
        plots=True,
        verbose=True,
        workers=2
    )

    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)

    # Get best model path
    best_model = Path(project) / name / "weights" / "best.pt"
    if best_model.exists():
        print(f"Best model: {best_model}")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Train YOLOv8 label detector")
    parser.add_argument("-d", "--data", default="YOLO/data/labels_dataset/data.yaml",
                       help="Path to data.yaml")
    parser.add_argument("-e", "--epochs", type=int, default=50,
                       help="Number of epochs")
    parser.add_argument("-b", "--batch", type=int, default=8,
                       help="Batch size")
    parser.add_argument("-s", "--imgsz", type=int, default=640,
                       help="Image size")
    parser.add_argument("-m", "--model", default="yolov8n.pt",
                       help="Base model")
    parser.add_argument("-n", "--name", default=None,
                       help="Experiment name")

    args = parser.parse_args()

    train_label_detector(
        data_yaml=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        model_base=args.model,
        name=args.name
    )


if __name__ == "__main__":
    main()
