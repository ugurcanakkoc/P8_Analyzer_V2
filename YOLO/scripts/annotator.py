"""
PDF YOLO Annotator Tool v3.0 (AI-Assisted Mode)
Features:
- AI-powered auto-detection using existing YOLO model
- Manual annotation with zoom, pan, and shortcuts
- Accept/reject workflow for AI suggestions
- Confidence threshold control
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw
import pymupdf
import os
import threading
from pathlib import Path

# Try to import YOLO - graceful fallback if not available
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[WARNING] ultralytics not installed. Auto-detect disabled. Install with: pip install ultralytics")


class PDFYOLOAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("🏷️ PDF YOLO Annotator v3.0 (AI-Assisted)")
        self.root.geometry("1500x900")

        # Directory Structure (relative to script location)
        script_dir = Path(__file__).parent.resolve()
        yolo_dir = script_dir.parent

        self.base_dir = yolo_dir / "data"
        self.images_dir = self.base_dir / "images" / "train"
        self.labels_dir = self.base_dir / "labels" / "train"
        self.classes_file = self.base_dir / "classes.txt"
        self.model_path = yolo_dir / "best.pt"

        print(f"[INFO] YOLO directory: {yolo_dir}")
        print(f"[INFO] Data directory: {self.base_dir}")

        self._setup_directories()

        # Durum Değişkenleri
        self.classes = self._load_classes()  # {name: id}
        self.current_class_id = 0
        self.pdf_doc = None
        self.current_page_index = 0
        self.rect_start = None
        self.current_rect = None
        self.annotations = []  # [(class_id, cx, cy, w, h)] - confirmed annotations

        # AI Suggestions
        self.suggestions = []  # [(class_id, cx, cy, w, h, confidence)] - pending suggestions
        self.selected_suggestion_idx = None
        self.confidence_threshold = 0.25

        # YOLO Model
        self.yolo_model = None
        self.model_loading = False
        self.model_classes = {}  # Model's class mapping

        # Görüntü ve Zoom
        self.original_image = None
        self.display_image = None
        self.tk_image = None
        self.zoom_level = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.pan_start = None

        self._build_ui()
        self._bind_shortcuts()

        # Load model in background
        if YOLO_AVAILABLE:
            self._load_model_async()

    def _setup_directories(self):
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.labels_dir, exist_ok=True)
        if not self.classes_file.exists():
            with open(self.classes_file, 'w') as f:
                f.write("PLC_Module\nTerminal\nContactor")

    def _load_classes(self):
        classes = {}
        if self.classes_file.exists():
            with open(self.classes_file, 'r') as f:
                lines = f.readlines()
                for idx, line in enumerate(lines):
                    name = line.strip()
                    if name:
                        classes[name] = idx
        return classes

    def _save_classes(self):
        sorted_classes = sorted(self.classes.items(), key=lambda x: x[1])
        with open(self.classes_file, 'w') as f:
            for name, _ in sorted_classes:
                f.write(f"{name}\n")

    def _load_model_async(self):
        """Load YOLO model in background thread"""
        # Get the script's directory for reliable path resolution
        script_dir = Path(__file__).parent.resolve()
        yolo_dir = script_dir.parent  # YOLO folder

        # Try multiple paths relative to script location
        possible_paths = [
            yolo_dir / "best.pt",
            yolo_dir / "runs" / "role_detection" / "weights" / "best.pt",
            yolo_dir / "customers" / "troester" / "models" / "plc_model.pt",
            self.model_path,  # Original relative path as fallback
        ]

        model_found = None
        for p in possible_paths:
            print(f"[DEBUG] Checking model path: {p} - exists: {p.exists()}")
            if p.exists():
                model_found = p
                break

        if not model_found:
            print("[ERROR] No YOLO model found in any location!")
            self._update_model_status("Model not found", "red")
            return

        self.model_path = model_found
        print(f"[INFO] Using model: {self.model_path}")

        self.model_loading = True
        self._update_model_status("⏳ Loading model...", "orange")

        def load():
            try:
                self.yolo_model = YOLO(str(self.model_path))
                # Get model's class names
                if hasattr(self.yolo_model, 'names'):
                    self.model_classes = self.yolo_model.names
                self.root.after(0, lambda: self._update_model_status("✅ Model ready", "green"))
                self.root.after(0, lambda: self.btn_auto_detect.config(state=tk.NORMAL))
            except Exception as e:
                self.root.after(0, lambda: self._update_model_status(f"❌ Load failed: {str(e)[:30]}", "red"))
            finally:
                self.model_loading = False

        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _update_model_status(self, text, color):
        """Update the model status label"""
        self.lbl_model_status.config(text=text, foreground=color)

    def _build_ui(self):
        # Sol Panel (Canvas)
        self.left_panel = ttk.Frame(self.root)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar'lar
        self.v_scroll = tk.Scrollbar(self.left_panel, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(self.left_panel, orient=tk.HORIZONTAL)

        self.canvas = tk.Canvas(self.left_panel, bg="#333333", cursor="cross",
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set)

        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse Olayları
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Zoom & Pan
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)

        # Sağ Panel (Kontroller)
        self.right_panel = ttk.Frame(self.root, width=320)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        self.right_panel.pack_propagate(False)

        # Başlık
        ttk.Label(self.right_panel, text="Kontrol Paneli", font=("Arial", 14, "bold")).pack(pady=10)

        # PDF Yükle
        ttk.Button(self.right_panel, text="📂 PDF Aç", command=self.load_pdf).pack(fill=tk.X, pady=5)

        # Navigasyon
        nav_frame = ttk.Frame(self.right_panel)
        nav_frame.pack(fill=tk.X, pady=10)
        ttk.Button(nav_frame, text="< (A)", command=self.prev_page, width=8).pack(side=tk.LEFT)
        self.lbl_page = ttk.Label(nav_frame, text="0/0", font=("Arial", 10, "bold"))
        self.lbl_page.pack(side=tk.LEFT, expand=True)
        ttk.Button(nav_frame, text="(D) >", command=self.next_page, width=8).pack(side=tk.LEFT)

        # === AI ASSIST SECTION ===
        ttk.Separator(self.right_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(self.right_panel, text="🤖 AI Assist", font=("Arial", 12, "bold")).pack(pady=5)

        # Model Status
        self.lbl_model_status = ttk.Label(self.right_panel, text="⏳ Initializing...", font=("Arial", 9))
        self.lbl_model_status.pack(pady=2)

        # Auto-Detect Button
        self.btn_auto_detect = ttk.Button(
            self.right_panel,
            text="🔍 Auto-Detect (Space)",
            command=self.run_auto_detect,
            state=tk.DISABLED
        )
        self.btn_auto_detect.pack(fill=tk.X, pady=5)

        # Confidence Threshold
        conf_frame = ttk.Frame(self.right_panel)
        conf_frame.pack(fill=tk.X, pady=5)
        ttk.Label(conf_frame, text="Confidence:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.lbl_conf_value = ttk.Label(conf_frame, text="25%", font=("Arial", 9, "bold"))
        self.lbl_conf_value.pack(side=tk.RIGHT)

        self.conf_slider = ttk.Scale(
            self.right_panel,
            from_=0.1,
            to=0.95,
            orient=tk.HORIZONTAL,
            command=self._on_confidence_change
        )
        self.conf_slider.set(0.25)
        self.conf_slider.pack(fill=tk.X)

        # Suggestions List
        ttk.Label(self.right_panel, text="Öneriler (Tıkla: Kabul):", font=("Arial", 9, "bold")).pack(pady=(10, 2))

        self.listbox_suggestions = tk.Listbox(self.right_panel, height=5, bg="#2a2a2a", fg="#00ff00", selectbackground="#005500")
        self.listbox_suggestions.pack(fill=tk.X)
        self.listbox_suggestions.bind("<<ListboxSelect>>", self.on_suggestion_select)
        self.listbox_suggestions.bind("<Double-Button-1>", self.accept_selected_suggestion)

        # Accept/Reject Buttons
        suggest_btn_frame = ttk.Frame(self.right_panel)
        suggest_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(suggest_btn_frame, text="✅ Kabul (Enter)", command=self.accept_selected_suggestion, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(suggest_btn_frame, text="❌ Reddet (X)", command=self.reject_selected_suggestion, width=12).pack(side=tk.LEFT, padx=2)

        ttk.Button(self.right_panel, text="✅ Tümünü Kabul (Ctrl+A)", command=self.accept_all_suggestions).pack(fill=tk.X, pady=2)
        ttk.Button(self.right_panel, text="❌ Tümünü Temizle", command=self.clear_all_suggestions).pack(fill=tk.X, pady=2)

        # === MANUAL ANNOTATION SECTION ===
        ttk.Separator(self.right_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(self.right_panel, text="✏️ Manuel Etiketleme", font=("Arial", 12, "bold")).pack(pady=5)

        # Sınıf Seçimi
        ttk.Label(self.right_panel, text="Sınıf (1-9):", font=("Arial", 9)).pack(pady=(5, 2))

        self.class_var = tk.StringVar()
        self.combo_classes = ttk.Combobox(self.right_panel, textvariable=self.class_var, state="readonly")
        self.combo_classes.pack(fill=tk.X)
        self.combo_classes.bind("<<ComboboxSelected>>", self.on_class_selected)

        ttk.Button(self.right_panel, text="➕ Yeni Sınıf", command=self.add_new_class).pack(fill=tk.X, pady=5)

        # Confirmed Labels
        ttk.Label(self.right_panel, text="Onaylı Etiketler:", font=("Arial", 9, "bold")).pack(pady=(10, 2))
        self.listbox_labels = tk.Listbox(self.right_panel, height=6)
        self.listbox_labels.pack(fill=tk.X)

        ttk.Button(self.right_panel, text="🗑️ Seçileni Sil (Del)", command=self.delete_selected_label).pack(fill=tk.X, pady=5)

        # Kaydet
        ttk.Separator(self.right_panel, orient='horizontal').pack(fill=tk.X, pady=10)
        self.btn_save = ttk.Button(self.right_panel, text="💾 KAYDET (S)", command=self.save_page_data, state=tk.DISABLED)
        self.btn_save.pack(fill=tk.X, ipady=10)

        # Kısayol Bilgisi
        info_text = """
Kısayollar:
Space: Auto-Detect
Enter: Kabul Et
X: Reddet
Ctrl+A: Tümünü Kabul
Mouse Teker: Zoom
Orta Tuş: Pan
1-9: Sınıf Seç
A/D: Sayfa Gezin
S: Kaydet | Del: Sil
        """
        ttk.Label(self.right_panel, text=info_text, font=("Arial", 7), justify=tk.LEFT).pack(side=tk.BOTTOM, pady=5)

        self._update_class_combo()

    def _bind_shortcuts(self):
        self.root.bind("<Right>", lambda e: self.next_page())
        self.root.bind("<d>", lambda e: self.next_page())
        self.root.bind("<Left>", lambda e: self.prev_page())
        self.root.bind("<a>", lambda e: self.prev_page())
        self.root.bind("<s>", lambda e: self.save_page_data())
        self.root.bind("<Delete>", lambda e: self.delete_selected_label())
        self.root.bind("<space>", lambda e: self.run_auto_detect())
        self.root.bind("<Return>", lambda e: self.accept_selected_suggestion())
        self.root.bind("<x>", lambda e: self.reject_selected_suggestion())
        self.root.bind("<Control-a>", lambda e: self.accept_all_suggestions())

        # Sayı tuşları (1-9)
        for i in range(1, 10):
            self.root.bind(str(i), lambda e, idx=i-1: self.select_class_by_index(idx))

    def _on_confidence_change(self, value):
        """Update confidence threshold"""
        self.confidence_threshold = float(value)
        self.lbl_conf_value.config(text=f"{int(self.confidence_threshold * 100)}%")
        # Re-filter suggestions if any exist
        if self.suggestions:
            self._filter_suggestions_by_confidence()

    def _filter_suggestions_by_confidence(self):
        """Filter and redraw suggestions based on current threshold"""
        self._update_suggestions_listbox()
        self.redraw_boxes()

    # === AI DETECTION METHODS ===

    def run_auto_detect(self):
        """Run YOLO inference on current page"""
        if not self.original_image:
            self._show_toast("Önce bir PDF açın!")
            return

        if not self.yolo_model:
            self._show_toast("Model yüklenmedi!")
            return

        if self.model_loading:
            self._show_toast("Model yükleniyor, bekleyin...")
            return

        self._show_toast("🔍 Algılama yapılıyor...")
        self.btn_auto_detect.config(state=tk.DISABLED)

        def detect():
            try:
                print(f"[DEBUG] Running inference on image size: {self.original_image.size}")
                print(f"[DEBUG] Model classes: {self.model_classes}")

                # Run inference with minimum confidence threshold
                results = self.yolo_model(self.original_image, verbose=False, conf=self.confidence_threshold)

                print(f"[DEBUG] Got {len(results)} result objects")

                new_suggestions = []
                for result in results:
                    img_w, img_h = self.original_image.size

                    # Check for OBB (Oriented Bounding Box) results first
                    if hasattr(result, 'obb') and result.obb is not None and len(result.obb) > 0:
                        obb = result.obb
                        print(f"[DEBUG] OBB detections found: {len(obb)}")

                        for i in range(len(obb)):
                            conf = float(obb.conf[i])
                            cls_id = int(obb.cls[i])
                            cls_name = self.model_classes.get(cls_id, f"class_{cls_id}")

                            # Get bounding box from OBB corners
                            if hasattr(obb, 'xyxyxyxy'):
                                corners = obb.xyxyxyxy[i].tolist()
                                xs = [c[0] for c in corners]
                                ys = [c[1] for c in corners]
                                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                            elif hasattr(obb, 'xyxy'):
                                x1, y1, x2, y2 = obb.xyxy[i].tolist()
                            else:
                                # Use xywhr (center, width, height, rotation)
                                xywhr = obb.xywhr[i].tolist()
                                cx_px, cy_px, w_px, h_px, _ = xywhr
                                x1, y1 = cx_px - w_px/2, cy_px - h_px/2
                                x2, y2 = cx_px + w_px/2, cy_px + h_px/2

                            print(f"[DEBUG] OBB Detection: {cls_name} (id={cls_id}) conf={conf:.2f} box=[{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}]")

                            # Convert to normalized center format
                            cx = ((x1 + x2) / 2) / img_w
                            cy = ((y1 + y2) / 2) / img_h
                            w = (x2 - x1) / img_w
                            h = (y2 - y1) / img_h

                            new_suggestions.append((cls_id, cx, cy, w, h, conf))

                    # Fall back to standard boxes if no OBB
                    elif hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes
                        print(f"[DEBUG] Box detections found: {len(boxes)}")

                        for i in range(len(boxes)):
                            conf = float(boxes.conf[i])
                            cls_id = int(boxes.cls[i])
                            cls_name = self.model_classes.get(cls_id, f"class_{cls_id}")

                            # Get box coordinates (xyxy format)
                            x1, y1, x2, y2 = boxes.xyxy[i].tolist()

                            print(f"[DEBUG] Box Detection: {cls_name} (id={cls_id}) conf={conf:.2f} box=[{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}]")

                            # Convert to normalized center format
                            cx = ((x1 + x2) / 2) / img_w
                            cy = ((y1 + y2) / 2) / img_h
                            w = (x2 - x1) / img_w
                            h = (y2 - y1) / img_h

                            new_suggestions.append((cls_id, cx, cy, w, h, conf))
                    else:
                        print("[DEBUG] No detections (neither OBB nor boxes)")

                print(f"[DEBUG] Total suggestions: {len(new_suggestions)}")

                # Update UI on main thread
                self.root.after(0, lambda: self._apply_detection_results(new_suggestions))

            except Exception as e:
                self.root.after(0, lambda: self._show_toast(f"Hata: {str(e)[:30]}"))
                self.root.after(0, lambda: self.btn_auto_detect.config(state=tk.NORMAL))

        thread = threading.Thread(target=detect, daemon=True)
        thread.start()

    def _apply_detection_results(self, new_suggestions):
        """Apply detection results to UI"""
        self.suggestions = new_suggestions
        self._update_suggestions_listbox()
        self.redraw_boxes()

        count = len([s for s in self.suggestions if s[5] >= self.confidence_threshold])
        self._show_toast(f"✅ {count} öneri bulundu!")
        self.btn_auto_detect.config(state=tk.NORMAL)

    def _update_suggestions_listbox(self):
        """Update the suggestions listbox"""
        self.listbox_suggestions.delete(0, tk.END)

        for i, (cls_id, cx, cy, w, h, conf) in enumerate(self.suggestions):
            if conf < self.confidence_threshold:
                continue

            # Get class name from model or our classes
            if cls_id in self.model_classes:
                cls_name = self.model_classes[cls_id]
            else:
                cls_name = next((k for k, v in self.classes.items() if v == cls_id), f"Class_{cls_id}")

            self.listbox_suggestions.insert(tk.END, f"[{i}] {cls_name} ({conf:.0%})")

    def on_suggestion_select(self, event):
        """Handle suggestion selection"""
        sel = self.listbox_suggestions.curselection()
        if sel:
            # Parse the index from the listbox text
            text = self.listbox_suggestions.get(sel[0])
            idx = int(text.split("]")[0][1:])
            self.selected_suggestion_idx = idx
            self.redraw_boxes()

    def accept_selected_suggestion(self, event=None):
        """Accept the selected suggestion and add to annotations"""
        sel = self.listbox_suggestions.curselection()
        if not sel:
            return

        text = self.listbox_suggestions.get(sel[0])
        idx = int(text.split("]")[0][1:])

        if 0 <= idx < len(self.suggestions):
            cls_id, cx, cy, w, h, conf = self.suggestions[idx]

            # Map model class to our class if needed
            mapped_cls_id = self._map_model_class_to_local(cls_id)

            # Add to confirmed annotations
            self.annotations.append((mapped_cls_id, cx, cy, w, h))

            # Update confirmed labels listbox
            cls_name = next((k for k, v in self.classes.items() if v == mapped_cls_id), f"Class_{mapped_cls_id}")
            self.listbox_labels.insert(tk.END, cls_name)

            # Remove from suggestions
            del self.suggestions[idx]
            self._update_suggestions_listbox()
            self.redraw_boxes()
            self._show_toast(f"✅ {cls_name} kabul edildi!")

    def _map_model_class_to_local(self, model_cls_id):
        """Map model's class ID to our local class ID"""
        if model_cls_id in self.model_classes:
            model_cls_name = self.model_classes[model_cls_id]
            # Try to find matching class in our classes
            if model_cls_name in self.classes:
                return self.classes[model_cls_name]
            # Try case-insensitive match
            for name, local_id in self.classes.items():
                if name.lower() == model_cls_name.lower():
                    return local_id
        # Default: use as-is or first class
        return model_cls_id if model_cls_id < len(self.classes) else 0

    def reject_selected_suggestion(self, event=None):
        """Reject the selected suggestion"""
        sel = self.listbox_suggestions.curselection()
        if not sel:
            return

        text = self.listbox_suggestions.get(sel[0])
        idx = int(text.split("]")[0][1:])

        if 0 <= idx < len(self.suggestions):
            del self.suggestions[idx]
            self._update_suggestions_listbox()
            self.redraw_boxes()
            self._show_toast("❌ Öneri reddedildi")

    def accept_all_suggestions(self, event=None):
        """Accept all suggestions above threshold"""
        accepted = 0
        to_accept = [(i, s) for i, s in enumerate(self.suggestions) if s[5] >= self.confidence_threshold]

        for _, (cls_id, cx, cy, w, h, conf) in to_accept:
            mapped_cls_id = self._map_model_class_to_local(cls_id)
            self.annotations.append((mapped_cls_id, cx, cy, w, h))

            cls_name = next((k for k, v in self.classes.items() if v == mapped_cls_id), f"Class_{mapped_cls_id}")
            self.listbox_labels.insert(tk.END, cls_name)
            accepted += 1

        # Clear all suggestions
        self.suggestions = []
        self._update_suggestions_listbox()
        self.redraw_boxes()
        self._show_toast(f"✅ {accepted} öneri kabul edildi!")

    def clear_all_suggestions(self):
        """Clear all suggestions"""
        self.suggestions = []
        self._update_suggestions_listbox()
        self.redraw_boxes()
        self._show_toast("🗑️ Öneriler temizlendi")

    # === EXISTING METHODS (UPDATED) ===

    def select_class_by_index(self, index):
        names = list(self.classes.keys())
        if 0 <= index < len(names):
            name = names[index]
            self.combo_classes.set(name)
            self.current_class_id = self.classes[name]
            self._show_toast(f"Sınıf: {name}")

    def _show_toast(self, message):
        toast = self.canvas.create_text(
            self.canvas.winfo_width()/2, 30,
            text=message,
            fill="yellow",
            font=("Arial", 16, "bold"),
            tags="toast"
        )
        self.root.after(1500, lambda: self.canvas.delete(toast))

    def _update_class_combo(self):
        names = list(self.classes.keys())
        self.combo_classes['values'] = names
        if names:
            self.combo_classes.current(0)
            self.current_class_id = self.classes[names[0]]

    def add_new_class(self):
        new_class = simpledialog.askstring("Yeni Sınıf", "Sınıf Adı (Örn: Sigorta):")
        if new_class and new_class not in self.classes:
            new_id = len(self.classes)
            self.classes[new_class] = new_id
            self._save_classes()
            self._update_class_combo()
            self.combo_classes.set(new_class)
            self.current_class_id = new_id
            messagebox.showinfo("Bilgi", f"'{new_class}' eklendi (ID: {new_id})")

    def on_class_selected(self, event):
        name = self.class_var.get()
        self.current_class_id = self.classes[name]

    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        self.pdf_doc = pymupdf.open(file_path)
        self.pdf_name = Path(file_path).stem
        self.current_page_index = 0
        self.load_page(0)

    def load_page(self, index):
        if not self.pdf_doc:
            return
        if index < 0 or index >= len(self.pdf_doc):
            return

        self.current_page_index = index
        self.lbl_page.config(text=f"{index + 1}/{len(self.pdf_doc)}")

        # Yüksek Kaliteli Render (300 DPI)
        page = self.pdf_doc[index]
        zoom_matrix = pymupdf.Matrix(3, 3)
        pix = page.get_pixmap(matrix=zoom_matrix)
        self.original_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # Reset View
        self.zoom_level = 1.0
        screen_h = self.root.winfo_height() - 100
        if self.original_image.height > screen_h:
            self.zoom_level = screen_h / self.original_image.height

        self.pan_offset_x = 0
        self.pan_offset_y = 0

        # Clear annotations and suggestions
        self.annotations = []
        self.suggestions = []
        self.listbox_labels.delete(0, tk.END)
        self.listbox_suggestions.delete(0, tk.END)
        self.btn_save.config(state=tk.NORMAL)

        self._check_existing_labels()
        self.update_display()

    def update_display(self):
        if not self.original_image:
            return

        new_w = int(self.original_image.width * self.zoom_level)
        new_h = int(self.original_image.height * self.zoom_level)

        if new_w < 100:
            new_w = 100
        if new_h < 100:
            new_h = 100

        self.display_image = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.display_image)

        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.redraw_boxes()

    def redraw_boxes(self):
        """Draw both confirmed annotations and suggestions"""
        self.canvas.delete("box")
        self.canvas.delete("suggestion")

        if not self.original_image:
            return

        img_w, img_h = self.original_image.size

        # Draw confirmed annotations (solid lines)
        for ann in self.annotations:
            cls_id, cx, cy, w, h = ann
            self._draw_box(cls_id, cx, cy, w, h, img_w, img_h,
                          style="confirmed", tag="box")

        # Draw suggestions (dashed lines)
        for i, (cls_id, cx, cy, w, h, conf) in enumerate(self.suggestions):
            if conf < self.confidence_threshold:
                continue

            is_selected = (i == self.selected_suggestion_idx)
            self._draw_box(cls_id, cx, cy, w, h, img_w, img_h,
                          style="suggestion", tag="suggestion",
                          confidence=conf, is_selected=is_selected)

    def _draw_box(self, cls_id, cx, cy, w, h, img_w, img_h, style="confirmed", tag="box", confidence=None, is_selected=False):
        """Draw a bounding box on canvas"""
        # Normalize -> Original Pixel
        real_w = w * img_w
        real_h = h * img_h
        real_cx = cx * img_w
        real_cy = cy * img_h

        x1 = real_cx - real_w/2
        y1 = real_cy - real_h/2
        x2 = real_cx + real_w/2
        y2 = real_cy + real_h/2

        # Original Pixel -> Zoomed Screen
        sx1 = x1 * self.zoom_level
        sy1 = y1 * self.zoom_level
        sx2 = x2 * self.zoom_level
        sy2 = y2 * self.zoom_level

        if style == "confirmed":
            color = self.get_class_color(cls_id)
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                        outline=color, width=2, tags=tag)
        else:  # suggestion
            color = "#00FF00" if not is_selected else "#FFFF00"
            width = 2 if not is_selected else 3
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                        outline=color, width=width,
                                        dash=(6, 4), tags=tag)

            # Draw confidence label
            if confidence:
                # Get class name
                if cls_id in self.model_classes:
                    cls_name = self.model_classes[cls_id][:8]  # Truncate
                else:
                    cls_name = f"C{cls_id}"

                label = f"{cls_name} {confidence:.0%}"
                self.canvas.create_text(sx1 + 5, sy1 - 10,
                                       text=label, fill=color,
                                       font=("Arial", 9, "bold"),
                                       anchor=tk.W, tags=tag)

    def get_class_color(self, cls_id):
        colors = ["#FF0000", "#0066FF", "#00CC00", "#FFCC00", "#00CCCC", "#CC00CC", "#FF6600", "#6600FF"]
        return colors[cls_id % len(colors)]

    def _check_existing_labels(self):
        label_path = self.labels_dir / f"{self.pdf_name}_page_{self.current_page_index}.txt"
        if label_path.exists():
            with open(label_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) == 5:  # Standard YOLO format
                        cls_id = int(parts[0])
                        cx, cy, w, h = map(float, parts[1:])
                        self.annotations.append((cls_id, cx, cy, w, h))

                        cls_name = next((k for k, v in self.classes.items() if v == cls_id), str(cls_id))
                        self.listbox_labels.insert(tk.END, cls_name)

    def prev_page(self):
        self.load_page(self.current_page_index - 1)

    def next_page(self):
        self.load_page(self.current_page_index + 1)

    def on_zoom(self, event):
        if not self.original_image:
            return

        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_level *= factor
        self.update_display()

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_mouse_down(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        self.rect_start = (canvas_x, canvas_y)
        self.current_rect = self.canvas.create_rectangle(
            canvas_x, canvas_y, canvas_x, canvas_y,
            outline="white", width=2, dash=(4, 4)
        )

    def on_mouse_drag(self, event):
        if self.rect_start:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.current_rect,
                             self.rect_start[0], self.rect_start[1],
                             canvas_x, canvas_y)

    def on_mouse_up(self, event):
        if not self.rect_start:
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        x1, y1 = self.rect_start
        x2, y2 = canvas_x, canvas_y

        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])

        if (x2 - x1) < 5 or (y2 - y1) < 5:
            self.canvas.delete(self.current_rect)
            self.rect_start = None
            return

        self.canvas.delete(self.current_rect)
        self.rect_start = None

        self._add_annotation(x1, y1, x2, y2)
        self.redraw_boxes()

    def on_right_click(self, event):
        """Right-click: cancel drawing or clear selection"""
        if self.current_rect:
            self.canvas.delete(self.current_rect)
            self.rect_start = None
        else:
            # Deselect suggestion
            self.listbox_suggestions.selection_clear(0, tk.END)
            self.selected_suggestion_idx = None
            self.redraw_boxes()

    def _add_annotation(self, x1, y1, x2, y2):
        if not self.original_image:
            return

        real_x1 = x1 / self.zoom_level
        real_y1 = y1 / self.zoom_level
        real_x2 = x2 / self.zoom_level
        real_y2 = y2 / self.zoom_level

        img_w, img_h = self.original_image.size

        cx = ((real_x1 + real_x2) / 2) / img_w
        cy = ((real_y1 + real_y2) / 2) / img_h
        w = (real_x2 - real_x1) / img_w
        h = (real_y2 - real_y1) / img_h

        self.annotations.append((self.current_class_id, cx, cy, w, h))

        cls_name = self.class_var.get()
        self.listbox_labels.insert(tk.END, cls_name)

    def delete_selected_label(self):
        sel = self.listbox_labels.curselection()
        if not sel:
            return

        idx = sel[0]
        self.listbox_labels.delete(idx)
        del self.annotations[idx]
        self.redraw_boxes()

    def save_page_data(self):
        if not self.original_image:
            return
        if not self.annotations:
            if not messagebox.askyesno("Uyarı", "Hiç etiket yok. Yine de boş olarak kaydetmek ister misiniz?"):
                return

        base_name = f"{self.pdf_name}_page_{self.current_page_index}"

        # 1. Resmi Kaydet
        img_path = self.images_dir / f"{base_name}.jpg"
        self.original_image.save(img_path, quality=95)

        # 2. Etiketleri Kaydet
        txt_path = self.labels_dir / f"{base_name}.txt"
        with open(txt_path, 'w') as f:
            for ann in self.annotations:
                f.write(f"{ann[0]} {ann[1]:.6f} {ann[2]:.6f} {ann[3]:.6f} {ann[4]:.6f}\n")

        self._show_toast("💾 KAYDEDİLDİ!")
        self.btn_save.config(text="✅ KAYDEDİLDİ!", state=tk.DISABLED)
        self.root.after(1500, lambda: self.btn_save.config(text="💾 KAYDET (S)", state=tk.NORMAL))
        print(f"✅ Kaydedildi: {base_name} ({len(self.annotations)} etiket)")


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFYOLOAnnotator(root)
    root.mainloop()
