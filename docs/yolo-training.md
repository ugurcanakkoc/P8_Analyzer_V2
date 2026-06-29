# YOLO Training Workflow

Back-link: referenced from `CLAUDE.md`. Detailed workflow notes also live in `.serena/memories/yolo_training_workflow.md`.

Key scripts:
- `YOLO/scripts/generate_label_dataset.py` — Extract labels from PDFs
- `YOLO/scripts/split_dataset.py` — Split detection datasets
- `YOLO/scripts/train_label_detector.py` — Train detection models
- `YOLO/scripts/prepare_classification_dataset.py` — Prepare classification datasets
- `YOLO/scripts/train_multi_class.py` — Retrain multi-class model

```bash
# Example: Generate and train label detector (venv prefix mandatory)
./venv/Scripts/python.exe YOLO/scripts/generate_label_dataset.py data/ornek.pdf -o YOLO/data/labels_dataset
./venv/Scripts/python.exe YOLO/scripts/split_dataset.py YOLO/data/labels_dataset 0.15
./venv/Scripts/python.exe YOLO/scripts/train_label_detector.py -e 50 -b 8
```

Trained model artifact: `YOLO/best.pt`.
