# YOLO Training Workflow

## Directory Structure
```
YOLO/
├── data/
│   ├── labels_dataset/          # Label detection dataset
│   │   ├── images/train/        # Training images
│   │   ├── images/val/          # Validation images
│   │   ├── labels/train/        # YOLO format labels (.txt)
│   │   ├── labels/val/          # Validation labels
│   │   └── data.yaml            # Dataset config
│   └── page_classifier/         # Classification dataset
├── scripts/
│   ├── generate_label_dataset.py    # Generate labels from PDF
│   ├── split_dataset.py             # Split into train/val (detection)
│   ├── prepare_classification_dataset.py  # Split for classification
│   ├── train_label_detector.py      # Train detection model
│   └── train_classifier.py          # Train classification model
└── runs/                        # Training outputs
    └── label_detection/         # Detection experiments
```

## Dataset Generation

### For Detection (Labels, Components)
```bash
# Generate from PDF
python YOLO/scripts/generate_label_dataset.py data/ornek.pdf -o YOLO/data/labels_dataset

# Split into train/val (15% val)
python YOLO/scripts/split_dataset.py YOLO/data/labels_dataset 0.15
```

### For Classification (Page Types)
```bash
python YOLO/scripts/prepare_classification_dataset.py -i YOLO/data/classification_output/ornek_xxx
```

## Training Commands

### Detection Model
```bash
python YOLO/scripts/train_label_detector.py -d YOLO/data/labels_dataset/data.yaml -e 50 -b 8
```

### Classification Model  
```bash
python YOLO/scripts/train_classifier.py --data YOLO/data/page_classifier --epochs 30
```

## YOLO Label Format (Detection)
```
# class_id x_center y_center width height (normalized 0-1)
0 0.5 0.5 0.1 0.05
```

## Key Scripts Reference
- `generate_label_dataset.py` - Extracts labels from PDFs using LabelDetector regex
- `split_dataset.py` - Splits detection dataset (images/labels folders)
- `train_label_detector.py` - Trains YOLOv8 detection model
