"""
YOLOv8 Classification Training for Page Classification
=======================================================

Trains a classification model to distinguish between schematic and
non-schematic pages in P8-format PDF documents.

Features:
- Binary classification (schematic vs non_schematic)
- GPU-accelerated training with early stopping
- Transfer learning support
- Consistent with train_obb.py patterns

Usage:
    python train_page_classifier.py                    # Train with defaults
    python train_page_classifier.py --epochs 50        # Custom epochs
    python train_page_classifier.py --model yolov8s-cls  # Larger model
"""

import argparse
import sys
import shutil
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import torch
    from ultralytics import YOLO
except ImportError as e:
    print(f"[ERROR] Required package not installed: {e}")
    print("Install with: pip install ultralytics torch")
    sys.exit(1)


def get_device():
    """Detect best available device (reused from train_obb.py)."""
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"[GPU] {device_name} ({memory_gb:.1f} GB)")
        return 0  # CUDA device 0
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        print("[GPU] Apple Silicon MPS")
        return 'mps'
    else:
        print("[CPU] No GPU detected, using CPU (training will be slow)")
        return 'cpu'


def train_classifier(
    data_dir: str = None,
    epochs: int = 30,
    batch_size: int = 16,
    imgsz: int = 640,
    patience: int = 10,
    model_name: str = "yolov8n-cls",
    pretrained: str = None,
    project: str = None,
    name: str = "page_classifier"
):
    """
    Train YOLOv8 classification model for page classification.

    Args:
        data_dir: Path to dataset directory (with train/val/test subdirs)
        epochs: Number of training epochs
        batch_size: Batch size (reduce if OOM)
        imgsz: Image size
        patience: Early stopping patience
        model_name: YOLO classification model variant
        pretrained: Path to pretrained model (for transfer learning)
        project: Output project directory
        name: Experiment name
    """
    print("=" * 60)
    print("  YOLOv8 Classification Training - Page Classifier")
    print("=" * 60)

    # Paths
    yolo_dir = Path(__file__).parent.parent
    if data_dir is None:
        data_dir = yolo_dir / "data" / "page_classifier"
    else:
        data_dir = Path(data_dir)

    project = project or str(yolo_dir / "runs" / "classify")

    # Verify dataset exists
    train_dir = data_dir / "train"
    val_dir = data_dir / "val"

    if not train_dir.exists():
        print(f"[ERROR] Training directory not found: {train_dir}")
        print("Run prepare_classification_dataset.py first.")
        sys.exit(1)

    # Count images per class
    train_schematic = len(list((train_dir / "schematic").glob("*.png")))
    train_non_schematic = len(list((train_dir / "non_schematic").glob("*.png")))
    val_schematic = len(list((val_dir / "schematic").glob("*.png"))) if val_dir.exists() else 0
    val_non_schematic = len(list((val_dir / "non_schematic").glob("*.png"))) if val_dir.exists() else 0

    print(f"\n[CONFIG]")
    print(f"  Dataset: {data_dir}")
    print(f"  Output: {project}/{name}")
    print(f"  Epochs: {epochs}")
    print(f"  Batch: {batch_size}")
    print(f"  Image Size: {imgsz}")
    print(f"  Patience: {patience}")
    print(f"  Model: {model_name}")

    print(f"\n[DATASET]")
    print(f"  Train: {train_schematic} schematic, {train_non_schematic} non-schematic")
    print(f"  Val: {val_schematic} schematic, {val_non_schematic} non-schematic")
    print(f"  Total: {train_schematic + train_non_schematic + val_schematic + val_non_schematic}")

    # Device
    device = get_device()

    # Load model
    print(f"\n[MODEL] Loading base model...")
    if pretrained and Path(pretrained).exists():
        print(f"  Transfer learning from: {pretrained}")
        model = YOLO(pretrained)
    else:
        print(f"  Using {model_name}")
        model = YOLO(model_name)

    # Training arguments
    train_args = {
        'data': str(data_dir),
        'epochs': epochs,
        'batch': batch_size,
        'imgsz': imgsz,
        'device': device,
        'patience': patience,

        # Output
        'project': project,
        'name': name,
        'exist_ok': True,
        'save': True,

        # Optimization
        'optimizer': 'AdamW',
        'lr0': 0.001,
        'lrf': 0.01,

        # Augmentation for classification (documents)
        'hsv_h': 0.0,        # No hue changes (preserve colors)
        'hsv_s': 0.3,        # Some saturation variation
        'hsv_v': 0.4,        # Brightness variation
        'degrees': 0.0,      # No rotation (preserve layout)
        'translate': 0.1,    # Small translations
        'scale': 0.2,        # Scale variation
        'flipud': 0.0,       # No vertical flip
        'fliplr': 0.0,       # No horizontal flip

        # Performance
        'workers': 4,
        'verbose': True,
        'plots': True,
    }

    print(f"\n[TRAINING] Starting...")
    print("-" * 60)

    try:
        results = model.train(**train_args)

        print("\n" + "=" * 60)
        print("  TRAINING COMPLETE!")
        print("=" * 60)

        # Results summary
        best_model = Path(project) / name / "weights" / "best.pt"
        print(f"\n[RESULTS]")
        print(f"  Best model: {best_model}")

        if hasattr(results, 'results_dict'):
            metrics = results.results_dict
            top1_acc = metrics.get('metrics/accuracy_top1', 'N/A')
            top5_acc = metrics.get('metrics/accuracy_top5', 'N/A')
            print(f"  Top-1 Accuracy: {top1_acc}")
            print(f"  Top-5 Accuracy: {top5_acc}")

        # Copy best model to convenient location
        if best_model.exists():
            target = yolo_dir / "page_classifier.pt"
            shutil.copy(best_model, target)
            print(f"  Copied to: {target}")

        return results

    except Exception as e:
        print(f"\n[ERROR] Training failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Train YOLOv8 page classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_page_classifier.py                      # Train with defaults
  python train_page_classifier.py --epochs 50          # Custom epochs
  python train_page_classifier.py --model yolov8s-cls  # Larger model
  python train_page_classifier.py --batch 8            # Smaller batch (less VRAM)

Models (smallest to largest):
  yolov8n-cls  - Nano (fastest, least accurate)
  yolov8s-cls  - Small
  yolov8m-cls  - Medium
  yolov8l-cls  - Large
  yolov8x-cls  - Extra Large (slowest, most accurate)
        """
    )

    parser.add_argument("--epochs", type=int, default=30, help="Training epochs (default: 30)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (default: 16)")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size (default: 640)")
    parser.add_argument("--patience", type=int, default=10, help="Early stopping patience (default: 10)")
    parser.add_argument("--model", type=str, default="yolov8n-cls", help="YOLO model variant")
    parser.add_argument("--data", type=str, default=None, help="Dataset directory path")
    parser.add_argument("--pretrained", type=str, default=None, help="Pretrained model for transfer learning")
    parser.add_argument("--project", type=str, default=None, help="Output project directory")
    parser.add_argument("--name", type=str, default="page_classifier", help="Experiment name")

    args = parser.parse_args()

    results = train_classifier(
        data_dir=args.data,
        epochs=args.epochs,
        batch_size=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        model_name=args.model,
        pretrained=args.pretrained,
        project=args.project,
        name=args.name
    )

    if results:
        print("\n[NEXT STEPS]")
        print("1. Review training curves in runs/classify/page_classifier/")
        print("2. Test model on new PDFs using the trained classifier")
        print("3. Add more training data if accuracy is below 90%")
    else:
        print("\n[FAILED] Check errors above and fix issues before retraining")


if __name__ == "__main__":
    main()
