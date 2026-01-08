"""
YOLOv8-OBB Training Script for P8 Electrical Schematics
========================================================

Trains an Oriented Bounding Box (OBB) model for detecting electrical
components in P8-format schematic diagrams.

Features:
- OBB detection for rotated components
- Optimized for small objects (terminals, pins)
- No rotation/flip augmentation (preserves symbol meaning)
- GPU-accelerated training with early stopping
- Auto-converts standard labels to OBB format if needed

Why OBB for Electrical Schematics:
- Tighter bounding boxes = better detection of closely-packed components
- Handles rotated terminals and connectors
- More precise localization for small objects (pins, terminals)
- Better NMS (Non-Maximum Suppression) due to less overlap

Usage:
    python train_obb.py [--epochs 100] [--batch 8] [--imgsz 1280]
    python train_obb.py --convert-only  # Just convert labels, don't train
"""

import argparse
import sys
import shutil
from pathlib import Path
from typing import List, Tuple, Optional

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


# =============================================================================
# Label Format Conversion Utilities
# =============================================================================

def detect_label_format(label_path: Path) -> Optional[str]:
    """
    Detect if a label file is in standard YOLO or OBB format.

    Returns: 'standard' (5 values), 'obb' (9 values), or None if empty/invalid
    """
    try:
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    return 'standard'
                elif len(parts) == 9:
                    return 'obb'
    except Exception:
        pass
    return None


def standard_to_obb(cx: float, cy: float, w: float, h: float) -> Tuple[float, ...]:
    """
    Convert standard YOLO format (center_x, center_y, width, height) to OBB format.

    For axis-aligned boxes, the OBB corners are simply the rectangle corners:
    - Top-left, Top-right, Bottom-right, Bottom-left

    Returns: (x1, y1, x2, y2, x3, y3, x4, y4)
    """
    half_w = w / 2
    half_h = h / 2

    # 4 corners (clockwise from top-left)
    x1, y1 = cx - half_w, cy - half_h  # Top-left
    x2, y2 = cx + half_w, cy - half_h  # Top-right
    x3, y3 = cx + half_w, cy + half_h  # Bottom-right
    x4, y4 = cx - half_w, cy + half_h  # Bottom-left

    return (x1, y1, x2, y2, x3, y3, x4, y4)


def convert_label_file(label_path: Path, backup: bool = True) -> bool:
    """
    Convert a single label file from standard to OBB format.

    Args:
        label_path: Path to the label file
        backup: If True, create a .bak backup before converting

    Returns: True if converted, False if already OBB or error
    """
    current_format = detect_label_format(label_path)

    if current_format == 'obb':
        return False  # Already OBB
    elif current_format != 'standard':
        print(f"  [SKIP] {label_path.name}: Unknown format or empty")
        return False

    try:
        with open(label_path, 'r') as f:
            lines = f.readlines()

        # Backup
        if backup:
            backup_path = label_path.with_suffix('.txt.bak')
            shutil.copy(label_path, backup_path)

        # Convert
        obb_lines = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue

            class_id = parts[0]
            cx, cy, w, h = map(float, parts[1:5])
            corners = standard_to_obb(cx, cy, w, h)

            # Format: class_id x1 y1 x2 y2 x3 y3 x4 y4
            obb_line = f"{class_id} " + " ".join(f"{c:.6f}" for c in corners)
            obb_lines.append(obb_line)

        # Write
        with open(label_path, 'w') as f:
            f.write("\n".join(obb_lines) + "\n")

        return True

    except Exception as e:
        print(f"  [ERROR] {label_path.name}: {e}")
        return False


def convert_labels_to_obb(data_dir: Path, splits: List[str] = None, backup: bool = True) -> dict:
    """
    Convert all standard YOLO labels to OBB format.

    Args:
        data_dir: Path to data directory (contains labels/ subdirectory)
        splits: List of splits to convert (default: ['train', 'val', 'test'])
        backup: Create backups of original files

    Returns: Dictionary with conversion statistics
    """
    splits = splits or ['train', 'val', 'test']
    stats = {'converted': 0, 'already_obb': 0, 'skipped': 0, 'errors': 0}

    print(f"\n[CONVERT] Converting labels to OBB format...")
    print(f"  Data directory: {data_dir}")
    print(f"  Splits: {splits}")
    print(f"  Backup: {backup}")

    for split in splits:
        labels_dir = data_dir / "labels" / split
        if not labels_dir.exists():
            continue

        print(f"\n  Processing {split}/...")

        for label_path in labels_dir.glob("*.txt"):
            if label_path.suffix == '.bak':
                continue

            result = convert_label_file(label_path, backup=backup)
            if result:
                stats['converted'] += 1
                print(f"    ✓ {label_path.name}")
            else:
                fmt = detect_label_format(label_path)
                if fmt == 'obb':
                    stats['already_obb'] += 1
                else:
                    stats['skipped'] += 1

    print(f"\n[CONVERT SUMMARY]")
    print(f"  Converted: {stats['converted']}")
    print(f"  Already OBB: {stats['already_obb']}")
    print(f"  Skipped: {stats['skipped']}")

    return stats


def get_device():
    """Detect best available device."""
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


def train_obb(
    data_yaml: str = None,
    epochs: int = 100,
    batch_size: int = 8,
    imgsz: int = 1280,
    patience: int = 30,
    pretrained: str = None,
    project: str = None,
    name: str = "p8_components_obb"
):
    """
    Train YOLOv8-OBB model for P8 schematic component detection.

    Args:
        data_yaml: Path to dataset configuration YAML
        epochs: Number of training epochs
        batch_size: Batch size (reduce if OOM)
        imgsz: Image size (larger = better for small objects)
        patience: Early stopping patience
        pretrained: Path to pretrained model (for transfer learning)
        project: Output project directory
        name: Experiment name
    """
    print("=" * 60)
    print("  YOLOv8-OBB Training for P8 Electrical Schematics")
    print("=" * 60)

    # Paths
    yolo_dir = Path(__file__).parent.parent
    data_yaml = data_yaml or str(yolo_dir / "data" / "dataset.yaml")
    project = project or str(yolo_dir / "runs" / "obb")

    # Check dataset exists
    if not Path(data_yaml).exists():
        print(f"[ERROR] Dataset config not found: {data_yaml}")
        print("Create it with the proper directory structure first.")
        sys.exit(1)

    print(f"\n[CONFIG]")
    print(f"  Dataset: {data_yaml}")
    print(f"  Output: {project}/{name}")
    print(f"  Epochs: {epochs}")
    print(f"  Batch: {batch_size}")
    print(f"  Image Size: {imgsz}")
    print(f"  Patience: {patience}")

    # Device
    device = get_device()

    # Load model
    print(f"\n[MODEL] Loading base model...")
    if pretrained and Path(pretrained).exists():
        print(f"  Transfer learning from: {pretrained}")
        model = YOLO(pretrained)
    else:
        # Use YOLOv8n-obb as base (small, fast, good for starting)
        print("  Using yolov8n-obb.pt (nano OBB model)")
        model = YOLO("yolov8n-obb.pt")

    # Training arguments optimized for electrical schematics
    train_args = {
        'data': data_yaml,
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
        'save_period': 10,

        # Optimization
        'optimizer': 'AdamW',
        'lr0': 0.001,
        'lrf': 0.01,
        'momentum': 0.937,
        'weight_decay': 0.0005,

        # Augmentation - CRITICAL for schematics
        # NO rotation/flip - symbols have directional meaning!
        'degrees': 0.0,      # No rotation
        'flipud': 0.0,       # No vertical flip
        'fliplr': 0.0,       # No horizontal flip

        # Safe augmentations for schematics
        'hsv_h': 0.015,      # Slight hue variation
        'hsv_s': 0.5,        # Saturation variation
        'hsv_v': 0.4,        # Value/brightness variation
        'translate': 0.1,    # Small translations
        'scale': 0.3,        # Scale variation (0.7-1.3x)
        'mosaic': 1.0,       # Mosaic augmentation
        'mixup': 0.0,        # No mixup (confuses text/symbols)
        'copy_paste': 0.0,   # No copy-paste

        # Mosaic settings
        'close_mosaic': 15,  # Disable mosaic for last 15 epochs

        # Performance
        'workers': 4,
        'cache': True,       # Cache images in RAM
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
            mAP50 = metrics.get('metrics/mAP50(B)', 'N/A')
            mAP50_95 = metrics.get('metrics/mAP50-95(B)', 'N/A')
            print(f"  mAP@50: {mAP50}")
            print(f"  mAP@50-95: {mAP50_95}")

        # Copy best model to YOLO root for easy access
        if best_model.exists():
            import shutil
            target = yolo_dir / "best_p8.pt"
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
        description="Train YOLOv8-OBB for P8 schematics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_obb.py                          # Train with defaults
  python train_obb.py --epochs 50 --batch 16   # Custom training
  python train_obb.py --convert-only           # Just convert labels
  python train_obb.py --auto-convert           # Convert + train

Label Formats:
  Standard: class_id center_x center_y width height (5 values)
  OBB:      class_id x1 y1 x2 y2 x3 y3 x4 y4 (9 values)

OBB Benefits for Electrical Schematics:
  - Tighter bounding boxes for closely-packed components
  - Handles rotated terminals and connectors
  - Better detection of small objects (pins, terminals)
        """
    )

    # Training arguments
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs (default: 100)")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (default: 8)")
    parser.add_argument("--imgsz", type=int, default=1280, help="Image size (default: 1280)")
    parser.add_argument("--patience", type=int, default=30, help="Early stopping patience (default: 30)")
    parser.add_argument("--data", type=str, default=None, help="Dataset YAML path")
    parser.add_argument("--pretrained", type=str, default=None, help="Pretrained model path for transfer learning")
    parser.add_argument("--project", type=str, default=None, help="Output project directory")
    parser.add_argument("--name", type=str, default="p8_components_obb", help="Experiment name")

    # Conversion arguments
    parser.add_argument("--convert-only", action="store_true",
                        help="Only convert labels from standard to OBB format, don't train")
    parser.add_argument("--auto-convert", action="store_true",
                        help="Auto-convert standard labels to OBB before training")
    parser.add_argument("--no-backup", action="store_true",
                        help="Don't create backup of original labels during conversion")

    args = parser.parse_args()

    # Determine data directory
    yolo_dir = Path(__file__).parent.parent
    data_dir = yolo_dir / "data"

    # Convert-only mode
    if args.convert_only:
        print("=" * 60)
        print("  Label Format Conversion (Standard → OBB)")
        print("=" * 60)
        stats = convert_labels_to_obb(data_dir, backup=not args.no_backup)
        if stats['converted'] > 0:
            print("\n[SUCCESS] Labels converted to OBB format")
            print("You can now run training: python train_obb.py")
        else:
            print("\n[INFO] No labels needed conversion")
        return

    # Auto-convert before training
    if args.auto_convert:
        print("\n[AUTO-CONVERT] Checking label formats...")
        stats = convert_labels_to_obb(data_dir, backup=not args.no_backup)

    # Train
    results = train_obb(
        data_yaml=args.data,
        epochs=args.epochs,
        batch_size=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        pretrained=args.pretrained,
        project=args.project,
        name=args.name
    )

    if results:
        print("\n[NEXT STEPS]")
        print("1. Review training curves in runs/obb/{name}/")
        print("2. Test model: python -c \"from ultralytics import YOLO; YOLO('best_p8.pt').predict('test_image.jpg')\"")
        print("3. Add more training data if accuracy is low")
    else:
        print("\n[FAILED] Check errors above and fix issues before retraining")
        print("\n[HINT] If you see format errors, try: python train_obb.py --convert-only")


if __name__ == "__main__":
    main()
