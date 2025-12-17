import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
import numpy as np
import random
import os
import glob
import heapq
import threading
import time
from pathlib import Path

# --- Helper Functions from process_image.py ---

def create_grid(canvas_size, grid_size):
    """Create a grid for pathfinding."""
    h, w = canvas_size
    gh, gw = h // grid_size, w // grid_size
    return np.zeros((gh, gw), dtype=np.uint8)

def mark_rect_on_grid(grid, rect, grid_size, margin=0):
    """Mark a rectangle as blocked on the grid."""
    x, y, w, h = rect
    gx1, gy1 = max(0, (x - margin) // grid_size), max(0, (y - margin) // grid_size)
    gx2, gy2 = min(grid.shape[1]-1, (x + w + margin) // grid_size), min(grid.shape[0]-1, (y + h + margin) // grid_size)
    grid[gy1:gy2+1, gx1:gx2+1] = 1

def mark_path_on_grid(grid, path, junctions):
    """Mark bends and endpoint as junctions, mark path as shared (value 2)."""
    for idx, (x, y) in enumerate(path):
        if idx == len(path) - 1:
            junctions.add((x, y))
            continue
        if 0 < idx < len(path) - 1:
            prev = path[idx - 1]
            curr = path[idx]
            nxt = path[idx + 1]
            if (curr[0] - prev[0], curr[1] - prev[1]) != (nxt[0] - curr[0], nxt[1] - curr[1]):
                junctions.add((x, y))
                continue
        grid[y, x] = 2

def point_to_grid(pt, grid_size):
    return (pt[0] // grid_size, pt[1] // grid_size)

def grid_to_point(gpt, grid_size):
    return (gpt[0] * grid_size + grid_size // 2, gpt[1] * grid_size + grid_size // 2)

def soften_l_bend_path(path, min_offset=3, max_offset=7):
    if len(path) < 3:
        return path
    bend_idx = None
    for i in range(1, len(path)-1):
        dx1 = path[i][0] - path[i-1][0]
        dy1 = path[i][1] - path[i-1][1]
        dx2 = path[i+1][0] - path[i][0]
        dy2 = path[i+1][1] - path[i][1]
        if (dx1, dy1) != (dx2, dy2):
            bend_idx = i
            break
    if bend_idx is None:
        return path
    offset = random.randint(min_offset, max_offset)
    new_bend_idx = max(min(len(path) - 2, bend_idx + offset), 1)
    if path[bend_idx-1][0] == path[bend_idx][0]:
        new_bend = (path[bend_idx][0], path[new_bend_idx][1])
    else:
        new_bend = (path[new_bend_idx][0], path[bend_idx][1])
    new_path = path[:new_bend_idx]
    new_path.append(new_bend)
    new_path.extend(path[new_bend_idx+1:])
    return new_path

def astar(grid, start, goal, junctions):
    h, w = grid.shape
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    directions = [(-1,0), (1,0), (0,-1), (0,1)]

    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]
        for dx, dy in directions:
            neighbor = (current[0]+dx, current[1]+dy)
            if 0 <= neighbor[0] < w and 0 <= neighbor[1] < h:
                cell_val = grid[neighbor[1], neighbor[0]]
                if cell_val == 1 and neighbor not in junctions and neighbor != goal:
                    continue
                move_cost = 1 if cell_val != 2 else 0.5
                tentative_g = g_score[current] + move_cost
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f, neighbor))
                    came_from[neighbor] = current
    return None

def calculate_anchors_for_symbol(symbol_img, rect, orientation):
    x, y, w, h = rect
    cx, cy = x + w // 2, y + h // 2
    if orientation == 'horizontal':
        anchors = [(x - 10, cy), (x + w + 10, cy)]
    else:
        anchors = [(cx, y - 10), (cx, y + h + 10)]
    return anchors

def add_lines_avoiding_symbols(image, symbol_masks, num_lines=15, color=(0, 0, 0), thickness=1, max_attempts=100):
    if not symbol_masks:
        combined_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    else:
        combined_mask = np.zeros_like(symbol_masks[0])
        for mask in symbol_masks:
            combined_mask = cv2.bitwise_or(combined_mask, mask)
    kernel = np.ones((7, 7), np.uint8)
    combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)
    h, w = image.shape[:2]
    lines_drawn = 0
    attempts = 0
    while lines_drawn < num_lines and attempts < max_attempts * num_lines:
        attempts += 1
        x1, y1 = random.randint(0, w - 1), random.randint(0, h - 1)
        x2, y2 = random.randint(0, w - 1), random.randint(0, h - 1)
        line_check_mask = np.zeros_like(combined_mask)
        cv2.line(line_check_mask, (x1, y1), (x2, y2), 255, thickness)
        buffered_line_mask = cv2.dilate(line_check_mask, kernel, iterations=1)
        if np.any(cv2.bitwise_and(combined_mask, buffered_line_mask)):
            continue
        cv2.line(image, (x1, y1), (x2, y2), color, thickness)
        combined_mask = cv2.bitwise_or(combined_mask, buffered_line_mask)
        lines_drawn += 1
    return image, combined_mask

def add_random_text(image, existing_elements_mask, num_texts=5, max_attempts=50):
    h, w = image.shape[:2]
    fonts = [cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_PLAIN, cv2.FONT_HERSHEY_DUPLEX]
    short_texts = ["T1", "CB-A", "SW-42", "FDR-1", "V2", "P-3", "-X1", "PE", "L1", "L2", "L3", "N"]
    long_texts = ["Substation", "Control", "Phase A", "Auxiliary", "Main Bus", "Feeder", "Motor Control", "Power Supply"]
    kernel = np.ones((7, 7), np.uint8)
    texts_drawn = 0
    attempts = 0
    while texts_drawn < num_texts and attempts < max_attempts * num_texts:
        attempts += 1
        font = random.choice(fonts)
        font_scale = random.uniform(0.6, 1.2)
        thickness = random.randint(1, 2)
        color = (random.randint(0, 50), random.randint(0, 50), random.randint(0, 50))
        text = random.choice(short_texts if random.random() < 0.5 else long_texts)
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        if w - text_w <= 0 or h - text_h <= 0: continue
        x = random.randint(0, w - text_w)
        y = random.randint(text_h, h - baseline)
        text_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.rectangle(text_mask, (x, y - text_h), (x + text_w, y + baseline), 255, -1)
        buffered_text_mask = cv2.dilate(text_mask, kernel, iterations=1)
        if np.any(cv2.bitwise_and(existing_elements_mask, buffered_text_mask)):
            continue
        cv2.putText(image, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)
        existing_elements_mask = cv2.bitwise_or(existing_elements_mask, buffered_text_mask)
        texts_drawn += 1
    return image

def extract_symbols(image_path, label_path):
    image = cv2.imread(image_path)
    if image is None: return [], (0, 0)
    h, w = image.shape[:2]
    symbols_with_classes = []
    if not os.path.exists(label_path): return [], (w, h)
    with open(label_path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 5:
            # Standard YOLO: class xc yc w h
            class_index = int(parts[0])
            xc, yc, nw, nh = map(float, parts[1:])
            x1 = xc - nw / 2
            y1 = yc - nh / 2
            x2 = xc + nw / 2
            y2 = yc + nh / 2
            poly_norm = np.array([
                [x1, y1], [x2, y1], [x2, y2], [x1, y2]
            ], dtype=np.float32)
        elif len(parts) >= 9:
            # OBB/Segmentation: class x1 y1 x2 y2 ...
            class_index = int(parts[0])
            poly_norm = np.array(parts[1:], dtype=np.float32).reshape(-1, 2)
        else:
            continue
        poly = (poly_norm * np.array([w, h])).astype(np.int32)
        rect = cv2.boundingRect(poly)
        x, y, rect_w, rect_h = rect
        if rect_w <= 0 or rect_h <= 0: continue
        poly_local = poly - np.array([x, y])
        cropped_symbol_bgr = image[y:y+rect_h, x:x+rect_w]
        if cropped_symbol_bgr.size == 0: continue
        cropped_symbol_bgra = cv2.cvtColor(cropped_symbol_bgr, cv2.COLOR_BGR2BGRA)
        mask = np.zeros((rect_h, rect_w), dtype=np.uint8)
        cv2.fillPoly(mask, [poly_local], (255, 255, 255))
        cropped_symbol_bgra[:, :, 3] = mask
        symbols_with_classes.append((class_index, cropped_symbol_bgra))
    return symbols_with_classes, (w, h)

def place_symbols_with_pathfinding(symbols_with_classes, canvas_size=(1024, 1024), max_attempts=100):
    canvas = np.ones((canvas_size[1], canvas_size[0], 4), dtype=np.uint8) * 255
    placed_symbols = []
    placed_masks = []
    
    canvas_w, canvas_h = canvas_size
    grid_size = 4
    grid = create_grid(canvas_size, grid_size)
    junctions = set()
    line_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)

    # Place symbols
    for class_index, symbol in symbols_with_classes:
        placed = False
        for _ in range(max_attempts):
            scale = random.uniform(0.7, 1.3)
            h, w = symbol.shape[:2]
            new_h, new_w = int(h * scale), int(w * scale)
            if new_h == 0 or new_w == 0: continue
            resized_symbol = cv2.resize(symbol, (new_w, new_h))
            angle = random.choice([0, 90, 180, 270])
            center = (new_w // 2, new_h // 2)
            rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
            cos = np.abs(rot_mat[0, 0])
            sin = np.abs(rot_mat[0, 1])
            out_w = int((new_h * sin) + (new_w * cos))
            out_h = int((new_h * cos) + (new_w * sin))
            rot_mat[0, 2] += (out_w / 2) - center[0]
            rot_mat[1, 2] += (out_h / 2) - center[1]
            rotated_symbol = cv2.warpAffine(resized_symbol, rot_mat, (out_w, out_h))
            if canvas_size[0] - out_w <= 0 or canvas_size[1] - out_h <= 0: continue
            rand_x = random.randint(0, canvas_size[0] - out_w)
            rand_y = random.randint(0, canvas_size[1] - out_h)
            new_rect = (rand_x, rand_y, out_w, out_h)
            overlap = False
            for existing_rect, _, _, _, _, _, _ in placed_symbols:
                if not (rand_x + out_w < existing_rect[0] or existing_rect[0] + existing_rect[2] < rand_x or
                       rand_y + out_h < existing_rect[1] or existing_rect[1] + existing_rect[3] < rand_y):
                    overlap = True
                    break
            if not overlap:
                orientation = 'horizontal' if angle in [90, 270] else 'vertical'
                anchors = calculate_anchors_for_symbol(rotated_symbol, new_rect, orientation)
                alpha = rotated_symbol[:, :, 3] / 255.0
                color = rotated_symbol[:, :, :3]
                for c in range(3):
                    canvas[rand_y:rand_y+out_h, rand_x:rand_x+out_w, c] = \
                        alpha * color[:, :, c] + \
                        (1 - alpha) * canvas[rand_y:rand_y+out_h, rand_x:rand_x+out_w, c]
                symbol_alpha_mask = rotated_symbol[:, :, 3]
                full_size_symbol_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
                full_size_symbol_mask[rand_y:rand_y+out_h, rand_x:rand_x+out_w] = symbol_alpha_mask
                placed_masks.append(full_size_symbol_mask)
                placed_symbols.append((new_rect, anchors, {'used_anchors': []}, class_index, rotated_symbol, rand_x, rand_y))
                placed = True
                break
    
    for rect, _, _, _, _, _, _ in placed_symbols:
        mark_rect_on_grid(grid, rect, grid_size, margin=grid_size)

    # Connect symbols
    num_symbols = len(placed_symbols)
    connected_symbols = set()
    if num_symbols > 1:
        nodes = list(range(num_symbols))
        random.shuffle(nodes)
        edges = []
        for i in range(1, num_symbols):
            j = random.randint(0, i - 1)
            edges.append((nodes[i], nodes[j]))
        
        for i, j in edges:
            symbol1_rect, symbol1_anchors, symbol1_data, _, _, _, _ = placed_symbols[i]
            symbol2_rect, symbol2_anchors, symbol2_data, _, _, _, _ = placed_symbols[j]
            found_path = False
            for p1 in symbol1_anchors:
                for p2 in symbol2_anchors:
                    if p1 in symbol1_data['used_anchors'] or p2 in symbol2_data['used_anchors']: continue
                    g_start = point_to_grid(p1, grid_size)
                    g_goal = point_to_grid(p2, grid_size)
                    h, w = grid.shape
                    if (g_start[0] < 0 or g_start[0] >= w or g_start[1] < 0 or g_start[1] >= h or
                        g_goal[0] < 0 or g_goal[0] >= w or g_goal[1] < 0 or g_goal[1] >= h): continue
                    original_start_val = grid[g_start[1], g_start[0]]
                    original_goal_val = grid[g_goal[1], g_goal[0]]
                    grid[g_start[1], g_start[0]] = 0
                    grid[g_goal[1], g_goal[0]] = 0
                    path = astar(grid, g_start, g_goal, junctions)
                    grid[g_start[1], g_start[0]] = original_start_val
                    grid[g_goal[1], g_goal[0]] = original_goal_val
                    if path is not None:
                        path = soften_l_bend_path(path)
                        symbol1_data['used_anchors'].append(p1)
                        symbol2_data['used_anchors'].append(p2)
                        pts = [grid_to_point(gpt, grid_size) for gpt in path]
                        temp_line_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
                        for k in range(len(pts) - 1):
                            cv2.line(canvas, pts[k], pts[k+1], (0, 0, 0), 2)
                            cv2.line(temp_line_mask, pts[k], pts[k+1], 255, 4)
                        kernel = np.ones((7, 7), np.uint8)
                        temp_line_mask = cv2.dilate(temp_line_mask, kernel, iterations=1)
                        line_mask = cv2.bitwise_or(line_mask, temp_line_mask)
                        mark_path_on_grid(grid, path, junctions)
                        connected_symbols.add(i)
                        connected_symbols.add(j)
                        found_path = True
                        break
                if found_path: break

    # Clean up unconnected
    if connected_symbols:
        for idx in range(len(placed_symbols)):
            if idx not in connected_symbols:
                rect, _, _, _, _, rand_x, rand_y = placed_symbols[idx]
                x, y, w, h = rect
                canvas[rand_y:rand_y+h, rand_x:rand_x+w] = [255, 255, 255, 255]
        
        new_labels = []
        new_placed_masks = []
        for idx in sorted(connected_symbols):
            rect, _, _, class_index, rotated_symbol, rand_x, rand_y = placed_symbols[idx]
            contours, _ = cv2.findContours(rotated_symbol[:, :, 3], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                main_contour = max(contours, key=cv2.contourArea)
                main_contour[:, :, 0] += rand_x
                main_contour[:, :, 1] += rand_y
                
                # Modified for Standard YOLO Output (xc yc w h)
                bx, by, bw, bh = cv2.boundingRect(main_contour)
                xc = (bx + bw / 2.0) / canvas_w
                yc = (by + bh / 2.0) / canvas_h
                wn = bw / float(canvas_w)
                hn = bh / float(canvas_h)
                
                label_str = f"{class_index} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}"
                new_labels.append(label_str)
            if idx < len(placed_masks):
                new_placed_masks.append(placed_masks[idx])
        
        if new_placed_masks:
            connected_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
            for idx in sorted(connected_symbols):
                if idx < len(placed_masks):
                    connected_mask = cv2.bitwise_or(connected_mask, placed_masks[idx])
            kernel = np.ones((15, 15), np.uint8)
            connected_mask = cv2.dilate(connected_mask, kernel, iterations=1)
            connected_mask = cv2.bitwise_or(connected_mask, line_mask)
        else:
            connected_mask = line_mask.copy()
        
        canvas = add_random_text(canvas, connected_mask, num_texts=random.randint(3, 9))
        return canvas, new_labels
    else:
        return canvas, []

# --- GUI Application ---

class SyntheticGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sentetik Veri Üretici (YOLO)")
        self.root.geometry("600x450")
        
        # Variables
        base_path = Path(__file__).resolve().parent.parent
        data_path = base_path / "data"
        
        self.source_dir = tk.StringVar(value=str(data_path))
        self.output_dir = tk.StringVar(value=str(data_path / "synthetic"))
        self.num_images = tk.IntVar(value=100)
        self.status_var = tk.StringVar(value="Hazır")
        self.is_running = False

        self.create_widgets()

    def create_widgets(self):
        # Source Directory
        frame_source = ttk.LabelFrame(self.root, text="Kaynak Veri Klasörü (Images/Labels)")
        frame_source.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(frame_source, textvariable=self.source_dir).pack(side="left", fill="x", expand=True, padx=5, pady=5)
        ttk.Button(frame_source, text="Seç", command=self.select_source_dir).pack(side="right", padx=5, pady=5)

        # Output Directory
        frame_output = ttk.LabelFrame(self.root, text="Çıktı Klasörü")
        frame_output.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(frame_output, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=5, pady=5)
        ttk.Button(frame_output, text="Seç", command=self.select_output_dir).pack(side="right", padx=5, pady=5)

        # Settings
        frame_settings = ttk.LabelFrame(self.root, text="Ayarlar")
        frame_settings.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_settings, text="Üretilecek Resim Sayısı:").pack(side="left", padx=5, pady=5)
        ttk.Entry(frame_settings, textvariable=self.num_images, width=10).pack(side="left", padx=5, pady=5)

        # Actions
        frame_actions = ttk.Frame(self.root)
        frame_actions.pack(fill="x", padx=10, pady=10)
        
        self.btn_generate = ttk.Button(frame_actions, text="🚀 Üretimi Başlat", command=self.start_generation_thread)
        self.btn_generate.pack(fill="x", ipady=5)

        # Log/Status
        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(self.root, textvariable=self.status_var).pack(anchor="w", padx=10)
        
        self.log_text = tk.Text(self.root, height=10, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def select_source_dir(self):
        d = filedialog.askdirectory()
        if d: self.source_dir.set(d)

    def select_output_dir(self):
        d = filedialog.askdirectory()
        if d: self.output_dir.set(d)

    def start_generation_thread(self):
        if self.is_running: return
        
        src = self.source_dir.get()
        out = self.output_dir.get()
        
        if not src or not os.path.exists(src):
            messagebox.showerror("Hata", "Geçerli bir kaynak klasörü seçin.")
            return
        if not out:
            messagebox.showerror("Hata", "Çıktı klasörü seçin.")
            return

        self.is_running = True
        self.btn_generate.config(state="disabled")
        self.progress["value"] = 0
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
        
        threading.Thread(target=self.run_generation, args=(src, out, self.num_images.get()), daemon=True).start()

    def run_generation(self, source_dir, output_dir, num_images):
        try:
            self.log(f"Kaynak taranıyor: {source_dir}")
            
            # Find images
            image_exts = ['*.png', '*.jpg', '*.jpeg']
            source_images = []
            # Look in root and 'images' subdir
            search_paths = [source_dir, os.path.join(source_dir, 'images'), os.path.join(source_dir, 'images', 'train')]
            
            for p in search_paths:
                if os.path.exists(p):
                    for ext in image_exts:
                        source_images.extend(glob.glob(os.path.join(p, ext)))
            
            if not source_images:
                self.log("❌ Resim bulunamadı!")
                return

            self.log(f"✅ {len(source_images)} kaynak resim bulundu.")
            
            # Extract symbols
            symbols_by_class = {}
            original_size = (1024, 1024)
            
            # Look for labels
            label_search_paths = [source_dir, os.path.join(source_dir, 'labels'), os.path.join(source_dir, 'labels', 'train')]
            
            extracted_count = 0
            for img_path in source_images:
                base_name = os.path.splitext(os.path.basename(img_path))[0]
                label_path = None
                
                for lp in label_search_paths:
                    candidate = os.path.join(lp, f"{base_name}.txt")
                    if os.path.exists(candidate):
                        label_path = candidate
                        break
                
                if not label_path:
                    continue
                    
                symbols, size = extract_symbols(img_path, label_path)
                if symbols:
                    original_size = size
                    for cls_idx, sym in symbols:
                        if cls_idx not in symbols_by_class: symbols_by_class[cls_idx] = []
                        symbols_by_class[cls_idx].append(sym)
                        extracted_count += 1
            
            self.log(f"✅ Toplam {extracted_count} sembol çıkarıldı.")
            for cls, lst in symbols_by_class.items():
                self.log(f"   - Sınıf {cls}: {len(lst)} adet")

            if not symbols_by_class:
                self.log("❌ Hiç sembol çıkarılamadı. Etiket dosyalarını kontrol edin.")
                return

            # Prepare output dirs
            out_img_dir = os.path.join(output_dir, 'images')
            out_lbl_dir = os.path.join(output_dir, 'labels')
            os.makedirs(out_img_dir, exist_ok=True)
            os.makedirs(out_lbl_dir, exist_ok=True)

            self.log(f"\n🚀 {num_images} adet sentetik veri üretiliyor...")
            
            available_classes = list(symbols_by_class.keys())
            
            for i in range(num_images):
                total_symbols = random.randint(4, 15)
                symbols_for_image = []
                
                # Distribute randomly
                for _ in range(total_symbols):
                    cls = random.choice(available_classes)
                    if symbols_by_class[cls]:
                        sym = random.choice(symbols_by_class[cls])
                        symbols_for_image.append((cls, sym))
                
                if not symbols_for_image: continue

                # Generate
                result_img, labels = place_symbols_with_pathfinding(symbols_for_image, canvas_size=original_size)
                
                # Save
                fname = f"synth_{int(time.time())}_{i}"
                cv2.imwrite(os.path.join(out_img_dir, f"{fname}.png"), result_img)
                with open(os.path.join(out_lbl_dir, f"{fname}.txt"), 'w') as f:
                    f.write("\n".join(labels))
                
                # Update UI
                progress = ((i + 1) / num_images) * 100
                self.progress["value"] = progress
                self.status_var.set(f"Üretiliyor: {i+1}/{num_images}")
                self.root.update_idletasks()
            
            self.log("\n✅ İşlem Tamamlandı!")
            self.status_var.set("Tamamlandı")
            messagebox.showinfo("Başarılı", f"{num_images} adet veri üretildi.\nKonum: {output_dir}")

        except Exception as e:
            self.log(f"❌ HATA: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_running = False
            self.btn_generate.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = SyntheticGeneratorGUI(root)
    root.mainloop()
