
import os
import numpy as np
from pathlib import Path
from collections import defaultdict

def analyze_labels():
    base_dir = Path(r"c:\Users\Ugur Can\Desktop\P8_Analyzer_V2\YOLO")
    classes_file = base_dir / "data" / "classes.txt"
    labels_dir = base_dir / "data" / "labels" / "train"

    # Load Classes
    classes = {}
    if classes_file.exists():
        with open(classes_file, 'r') as f:
            lines = f.readlines()
            for idx, line in enumerate(lines):
                if line.strip():
                    classes[idx] = line.strip()
    
    print(f"Loaded {len(classes)} classes.")

    # Data Containers
    class_stats = defaultdict(lambda: {'w': [], 'h': []})
    total_boxes = 0

    # Read Labels
    files = list(labels_dir.glob("*.txt"))
    print(f"Analyzing {len(files)} label files...\n")

    for file_path in files:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    # x, y, w, h
                    w = float(parts[3])
                    h = float(parts[4])
                    
                    class_stats[cls_id]['w'].append(w)
                    class_stats[cls_id]['h'].append(h)
                    total_boxes += 1

    # Generate Report
    print(f"Total Annotations: {total_boxes}")
    print("-" * 60)
    print(f"{'Class Name':<20} | {'Count':<5} | {'Avg W':<8} | {'Std W':<8} | {'Avg H':<8} | {'Std H':<8}")
    print("-" * 60)

    for cls_id in sorted(classes.keys()):
        name = classes[cls_id]
        stats = class_stats.get(cls_id)
        
        if not stats:
            print(f"{name:<20} | {0:<5} | {'-':<8} | {'-':<8} | {'-':<8} | {'-':<8}")
            continue

        widths = np.array(stats['w'])
        heights = np.array(stats['h'])
        
        avg_w = np.mean(widths)
        std_w = np.std(widths)
        avg_h = np.mean(heights)
        std_h = np.std(heights)

        print(f"{name:<20} | {len(widths):<5} | {avg_w:.4f}   | {std_w:.4f}   | {avg_h:.4f}   | {std_h:.4f}")
        
        # Check for outliers (heuristic: > 2 std dev)
        # simplistic check
        w_outliers = np.sum(np.abs(widths - avg_w) > 2 * std_w)
        h_outliers = np.sum(np.abs(heights - avg_h) > 2 * std_h)
        
        if w_outliers > 0 or h_outliers > 0:
            print(f"  ⚠ Alert: Potential outliers found for {name} (W:{w_outliers}, H:{h_outliers})")

    print("-" * 60)
    print("Interpretation:")
    print("Avg W/H: Normalized dimensions (0.0 - 1.0).")
    print("Std W/H: Standard deviation. Closer to 0 means higher consistency.")
    print("If Std is high (> 0.01), box sizes vary significantly.")

if __name__ == "__main__":
    analyze_labels()
