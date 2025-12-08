
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, Menu
from PIL import Image, ImageTk
import pymupdf
import os
import cv2
import json
import numpy as np
from pathlib import Path

# Ultralytics (YOLO) kütüphanesi varsa import et, yoksa hata vermesin
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

# RENK PALETİ GÜNCELLEMESİ (BEYAZ ZEMİN ÜZERİNE KOYU RENKLER)
# PDF Arkaplanı genelde beyaz olduğu için açık renkler (Sarı, Cyan vs.) yasak.
COLOR_PALETTE = [
    "#FF0000", # Kırmızı (Saf)
    "#0000FF", # Mavi (Saf)
    "#008000", # Koyu Yeşil
    "#800080", # Mor
    "#FF00FF", # Magenta (Koyu tonlarda durabilir)
    "#800000", # Bordo
    "#000080", # Lacivert
    "#FF4500", # OrangeRed (Koyu Turuncu)
    "#2F4F4F", # DarkSlateGray
    "#4B0082"  # Indigo
]

class SmartAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("🏷️ Smart Annotator v4.2 (Dark Colors + Arrow Keys)")
        self.root.geometry("1600x950")
        
        # --- DOSYA YOLU AYARLARI ---
        self.script_dir = Path(__file__).resolve().parent
        self.yolo_dir = self.script_dir.parent
        self.base_dir = self.yolo_dir / "data"
        
        self.images_dir = self.base_dir / "images" / "train"
        self.labels_dir = self.base_dir / "labels" / "train"
        self.classes_file = self.base_dir / "classes.txt"
        self.config_file = self.base_dir / "class_config.json"
        
        self._setup_directories()
        
        # Durum Değişkenleri
        self.classes = self._load_classes() 
        self.class_configs = self._load_config()
        self.current_class_id = 0
        self.pdf_doc = None
        self.pdf_name = ""
        self.current_page_index = 0
        
        # Etiketler ve Seçim
        self.annotations = [] # [(class_id, x_norm, y_norm, w_norm, h_norm)]
        self.selected_annotation_index = -1
        self.hovered_annotation_index = -1
        
        # Etkileşim Durumları
        self.drag_data = {"x": 0, "y": 0, "item": None, "mode": None} # mode: 'move' or 'resize'
        self.resize_handle = None 
        
        # Sabit Boyut Modu
        self.fixed_size_mode = tk.BooleanVar(value=True)
        self.fixed_width = tk.IntVar(value=50)
        self.fixed_height = tk.IntVar(value=50)

        # Görüntü
        self.original_image = None
        self.cv2_image = None
        self.display_image = None
        self.tk_image = None
        self.zoom_level = 1.0
        
        # AI Model
        self.model = None
        
        self._build_ui()
        self._bind_shortcuts()
        
    def _setup_directories(self):
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.labels_dir, exist_ok=True)
        if not self.classes_file.exists():
            with open(self.classes_file, 'w') as f:
                f.write("PLC_Module\nTerminal\nContactor\nFuse\nRelay")
    
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

    def _load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                try: return json.load(f)
                except: return {}
        return {}

    def _save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.class_configs, f, indent=4)

    def _update_dimensions_from_config(self, class_name):
        if class_name in self.class_configs:
            cfg = self.class_configs[class_name]
            self.fixed_width.set(cfg.get('w', 50))
            self.fixed_height.set(cfg.get('h', 50))

    def _save_current_dimensions_for_class(self):
        class_name = self.class_var.get()
        if not class_name: return
        w = self.fixed_width.get()
        h = self.fixed_height.get()
        self.class_configs[class_name] = {'w': w, 'h': h}
        self._save_config()
        messagebox.showinfo("Kaydedildi", f"'{class_name}' standart boyut: {w}x{h} px")
    
    def _build_ui(self):
        # --- Sol: Canvas ---
        self.left_panel = ttk.Frame(self.root)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.v_scroll = tk.Scrollbar(self.left_panel, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(self.left_panel, orient=tk.HORIZONTAL)
        
        self.canvas = tk.Canvas(self.left_panel, bg="#1e1e1e", cursor="tcross",
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set)
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Eventler
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.bind("<Motion>", self.on_mouse_move) # Hover için
        
        # --- Sağ: Kontroller ---
        style = ttk.Style()
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=3)

        self.right_panel = ttk.Frame(self.root, width=320)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        self.right_panel.pack_propagate(False)
        
        ttk.Label(self.right_panel, text="Smart Annotator v4", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        # Dosya
        frame_nav = ttk.LabelFrame(self.right_panel, text="Navigasyon")
        frame_nav.pack(fill=tk.X, pady=5)
        ttk.Button(frame_nav, text="📂 PDF Aç", command=self.load_pdf).pack(fill=tk.X, padx=5, pady=2)
        
        nav_btns = ttk.Frame(frame_nav)
        nav_btns.pack(fill=tk.X, pady=2)
        ttk.Button(nav_btns, text="< Geri", command=self.prev_page).pack(side=tk.LEFT, padx=5, expand=True)
        self.lbl_page = ttk.Label(nav_btns, text="0/0", font=("Arial", 10, "bold"))
        self.lbl_page.pack(side=tk.LEFT)
        ttk.Button(nav_btns, text="İleri >", command=self.next_page).pack(side=tk.LEFT, padx=5, expand=True)
        
        # Sınıf
        frame_cls = ttk.LabelFrame(self.right_panel, text="Sınıf (1-9)")
        frame_cls.pack(fill=tk.X, pady=5)
        self.class_var = tk.StringVar()
        self.combo_classes = ttk.Combobox(frame_cls, textvariable=self.class_var, state="readonly", font=("Segoe UI", 11))
        self.combo_classes.pack(fill=tk.X, padx=5, pady=2)
        self.combo_classes.bind("<<ComboboxSelected>>", self.on_class_selected)
        ttk.Button(frame_cls, text="➕ Yeni Sınıf", command=self.add_new_class).pack(fill=tk.X, padx=5, pady=2)

        # Kutu
        frame_box = ttk.LabelFrame(self.right_panel, text="Kutu Ayarı")
        frame_box.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(frame_box, text="Sabit Boyut (Sol-Alt)", variable=self.fixed_size_mode).pack(anchor="w", padx=5)
        
        box_sz = ttk.Frame(frame_box)
        box_sz.pack(fill=tk.X, padx=5)
        ttk.Entry(box_sz, textvariable=self.fixed_width, width=5).pack(side=tk.LEFT)
        ttk.Label(box_sz, text="x").pack(side=tk.LEFT, padx=2)
        ttk.Entry(box_sz, textvariable=self.fixed_height, width=5).pack(side=tk.LEFT)
        ttk.Button(frame_box, text="💾 Sınıf İçin Kaydet", command=self._save_current_dimensions_for_class).pack(fill=tk.X, padx=5, pady=2)

        # Araçlar
        frame_tools = ttk.LabelFrame(self.right_panel, text="Araçlar")
        frame_tools.pack(fill=tk.X, pady=5)
        ttk.Button(frame_tools, text="🔍 Benzerleri Bul", command=self.find_similar_context).pack(fill=tk.X, padx=5, pady=2)
        
        self.lbl_status = ttk.Label(frame_tools, text="Hazır", foreground="gray")
        self.lbl_status.pack(pady=2)

        # Liste
        frame_list = ttk.LabelFrame(self.right_panel, text="Etiketler")
        frame_list.pack(fill=tk.BOTH, expand=True, pady=5)
        self.listbox_labels = tk.Listbox(frame_list, font=("Consolas", 10))
        self.listbox_labels.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.listbox_labels.bind('<<ListboxSelect>>', self.on_listbox_select)
        
        ttk.Button(frame_list, text="Sil", command=self.delete_selected_label).pack(fill=tk.X, padx=5)
        
        # Kaydet
        self.btn_save = ttk.Button(self.right_panel, text="💾 KAYDET", command=self.save_page_data, state=tk.DISABLED, style="Big.TButton")
        self.btn_save.pack(fill=tk.X, ipady=5, pady=10)

        # Context Menu
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🔍 Benzerlerini Bul", command=self.find_similar_context)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ Sil", command=self.delete_selected_context)
        
        self._update_class_combo()

    def _bind_shortcuts(self):
        self.root.bind("<s>", lambda e: self.save_page_data())
        self.root.bind("<Delete>", lambda e: self.delete_selected_label())
        # Yön Tuşları ile Navigasyon
        self.root.bind("<Right>", lambda e: self.next_page())
        self.root.bind("<Left>", lambda e: self.prev_page())
        # Alternatifler de kalsın
        self.root.bind("<d>", lambda e: self.next_page())
        self.root.bind("<a>", lambda e: self.prev_page())
        for i in range(1, 10):
            self.root.bind(str(i), lambda e, idx=i-1: self.select_class_by_index(idx))

    # --- Core Functions ---
    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path: return
        self.pdf_doc = pymupdf.open(file_path)
        self.pdf_name = Path(file_path).stem
        self.load_page(0)
    
    def load_page(self, index):
        if not self.pdf_doc: return
        if index < 0 or index >= len(self.pdf_doc): return
        self.current_page_index = index
        self.lbl_page.config(text=f"{index + 1}/{len(self.pdf_doc)}")
        
        page = self.pdf_doc[index]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3))
        self.original_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self.cv2_image = cv2.cvtColor(np.array(self.original_image), cv2.COLOR_RGB2BGR)
        
        self.zoom_level = (self.root.winfo_height() - 50) / self.original_image.height
        if self.zoom_level > 1.5: self.zoom_level = 1.0
        
        self.annotations = []
        self.listbox_labels.delete(0, tk.END)
        self.btn_save.config(state=tk.NORMAL)
        self._load_existing_labels()
        self.update_display()
        
    def update_display(self):
        if not self.original_image: return
        w, h = self.original_image.size
        new_w, new_h = max(10, int(w*self.zoom_level)), max(10, int(h*self.zoom_level))
        
        self.display_image = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.display_image)
        
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.redraw_boxes()

    def get_color(self, cls_id):
        return COLOR_PALETTE[cls_id % len(COLOR_PALETTE)]

    def redraw_boxes(self):
        self.canvas.delete("box")
        self.canvas.delete("handle")
        self.canvas.delete("info")
        self.canvas.delete("delete_btn")
        
        img_w, img_h = self.original_image.size
        
        for i, ann in enumerate(self.annotations):
            class_id, cx, cy, w, h = ann
            
            cx_px, cy_px = cx * img_w, cy * img_h
            w_px, h_px = w * img_w, h * img_h
            
            x1 = (cx_px - w_px/2) * self.zoom_level
            y1 = (cy_px - h_px/2) * self.zoom_level
            x2 = (cx_px + w_px/2) * self.zoom_level
            y2 = (cy_px + h_px/2) * self.zoom_level
            
            col = self.get_color(class_id)
            width = 2
            
            is_selected = (i == self.selected_annotation_index)
            is_hovered = (i == self.hovered_annotation_index)
            
            if is_selected or is_hovered:
                width = 3
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=col, width=3, tags=("box", f"box_{i}"))
                
                # Boyut Metni (Mavi)
                real_w_int = int(w_px)
                real_h_int = int(h_px)
                dim_text = f"{real_w_int}x{real_h_int}"
                tx, ty = x1, y1 - 15
                self.canvas.create_text(tx, ty, text=dim_text, fill="blue", font=("Arial", 10, "bold"), anchor="sw", tags=("info", f"info_{i}"))
                
                # Silme Butonu (X)
                bx1, by1 = x2 - 5, y1 - 15
                bx2, by2 = x2 + 10, y1
                
                self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="red", outline="white", tags=("delete_btn", f"del_{i}"))
                self.canvas.create_text((bx1+bx2)/2, (by1+by2)/2, text="X", fill="white", font=("Arial", 8, "bold"), tags=("delete_btn", f"del_{i}"))

                if is_selected:
                    r = 4 
                    self.canvas.create_rectangle(x1-r, y1-r, x1+r, y1+r, fill="black", outline="white", tags=("handle", f"nw_{i}"))
                    self.canvas.create_rectangle(x2-r, y1-r, x2+r, y1+r, fill="black", outline="white", tags=("handle", f"ne_{i}"))
                    self.canvas.create_rectangle(x1-r, y2-r, x1+r, y2+r, fill="black", outline="white", tags=("handle", f"sw_{i}"))
                    self.canvas.create_rectangle(x2-r, y2-r, x2+r, y2+r, fill="black", outline="white", tags=("handle", f"se_{i}"))
            else:
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=col, width=width, tags=("box", f"box_{i}"))

    def on_mouse_move(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # Silme butonuna geldik mi?
        overlaps = self.canvas.find_overlapping(cx-1, cy-1, cx+1, cy+1)
        is_over_del = False
        for item in overlaps:
            tags = self.canvas.gettags(item)
            if "delete_btn" in tags:
                self.canvas.config(cursor="hand2")
                return # Üzerindeyiz

        # Bir kutunun üzerinde miyiz?
        img_w, img_h = self.original_image.size
        # Tersten kontrol (üstteki önce)
        found_idx = -1
        for i in range(len(self.annotations)-1, -1, -1):
            ann = self.annotations[i]
            # Basit geometri
            cx_px, cy_px = ann[1] * img_w, ann[2] * img_h
            w_px, h_px = ann[3] * img_w, ann[4] * img_h
            x1 = (cx_px - w_px/2) * self.zoom_level
            y1 = (cy_px - h_px/2) * self.zoom_level
            x2 = (cx_px + w_px/2) * self.zoom_level
            y2 = (cy_px + h_px/2) * self.zoom_level
            
            # X butonu alanı biraz daha geniş olabilir tolerans için
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                found_idx = i
                break
        
        if found_idx != self.hovered_annotation_index:
            self.hovered_annotation_index = found_idx
            self.redraw_boxes()
        
        if found_idx != -1:
            self.canvas.config(cursor="hand2")
        else:
            self.canvas.config(cursor="arrow")

    def on_left_down(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # 0. Silme Butonuna Tıklandı mı?
        clicks = self.canvas.find_overlapping(cx-1, cy-1, cx+1, cy+1)
        for item in clicks:
            tags = self.canvas.gettags(item)
            if "delete_btn" in tags:
                # tags: ("delete_btn", "del_5")
                tag = tags[1]
                idx = int(tag.split("_")[1])
                self.delete_annotation_by_index(idx)
                return

        # 1. Handle (Resize)
        for item in clicks:
            tags = self.canvas.gettags(item)
            if "handle" in tags:
                handle_tag = tags[1] 
                direction, idx_str = handle_tag.split("_")
                self.selected_annotation_index = int(idx_str)
                self.drag_data["mode"] = "resize"
                self.drag_data["handle"] = direction
                self.drag_data["idx"] = self.selected_annotation_index
                return

        # 2. Kutu Seç / Taşı
        img_w, img_h = self.original_image.size
        clicked_idx = -1
        for i in range(len(self.annotations)-1, -1, -1):
            ann = self.annotations[i]
            cx_px, cy_px = ann[1] * img_w, ann[2] * img_h
            w_px, h_px = ann[3] * img_w, ann[4] * img_h
            x1 = (cx_px - w_px/2) * self.zoom_level
            y1 = (cy_px - h_px/2) * self.zoom_level
            x2 = (cx_px + w_px/2) * self.zoom_level
            y2 = (cy_px + h_px/2) * self.zoom_level
            
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                clicked_idx = i
                break
        
        if clicked_idx != -1:
            self.selected_annotation_index = clicked_idx
            self.listbox_labels.selection_clear(0, tk.END)
            self.listbox_labels.selection_set(clicked_idx)
            self.listbox_labels.see(clicked_idx)
            self.redraw_boxes()
            
            self.drag_data["mode"] = "move"
            self.drag_data["start_x"] = cx
            self.drag_data["start_y"] = cy
            self.drag_data["idx"] = clicked_idx
            return

        # 3. Boşluk -> Yeni
        self.selected_annotation_index = -1
        self.listbox_labels.selection_clear(0, tk.END)
        self.redraw_boxes()
        
        if self.fixed_size_mode.get():
            fw = self.fixed_width.get()
            fh = self.fixed_height.get()
            screen_w = fw * self.zoom_level
            screen_h = fh * self.zoom_level
            x1 = cx
            y2 = cy 
            y1 = y2 - screen_h
            x2 = x1 + screen_w
            self._add_annotation_from_coords(x1, y1, x2, y2)
        else:
            self.rect_start = (cx, cy)
            self.current_rect_item = self.canvas.create_rectangle(cx, cy, cx, cy, outline="#00FF00", width=2, dash=(4,4))

    def on_mouse_drag(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        if self.drag_data["mode"] == "move":
            idx = self.drag_data["idx"]
            dx = (cx - self.drag_data["start_x"]) / self.zoom_level
            dy = (cy - self.drag_data["start_y"]) / self.zoom_level
            
            cls_id, ann_cx, ann_cy, ann_w, ann_h = self.annotations[idx]
            img_w, img_h = self.original_image.size
            
            # Pixel hesabı
            px_cx = ann_cx * img_w + dx
            px_cy = ann_cy * img_h + dy
            
            self.annotations[idx] = (cls_id, px_cx/img_w, px_cy/img_h, ann_w, ann_h)
            
            self.drag_data["start_x"] = cx
            self.drag_data["start_y"] = cy
            self.redraw_boxes() # Canlı güncelleme
            return
            
        if self.drag_data["mode"] == "resize":
            idx = self.drag_data["idx"]
            handle = self.drag_data["handle"]
            
            img_w, img_h = self.original_image.size
            cls_id, norm_cx, norm_cy, norm_w, norm_h = self.annotations[idx]
            
            px_cx = norm_cx * img_w
            px_cy = norm_cy * img_h
            px_w = norm_w * img_w
            px_h = norm_h * img_h
            
            x1 = px_cx - px_w/2
            y1 = px_cy - px_h/2
            x2 = px_cx + px_w/2
            y2 = px_cy + px_h/2
            
            mx = cx / self.zoom_level
            my = cy / self.zoom_level
            
            if handle == 'nw': x1, y1 = mx, my
            elif handle == 'ne': x2, y1 = mx, my
            elif handle == 'sw': x1, y2 = mx, my
            elif handle == 'se': x2, y2 = mx, my
                
            new_w = abs(x2 - x1)
            new_h = abs(y2 - y1)
            new_cx = (x1 + x2) / 2
            new_cy = (y1 + y2) / 2
            
            self.annotations[idx] = (cls_id, new_cx / img_w, new_cy / img_h, new_w / img_w, new_h / img_h)
            self.redraw_boxes() # Canlı güncelleme (Text de güncellenir)
            return

        if self.rect_start:
            self.canvas.coords(self.current_rect_item, self.rect_start[0], self.rect_start[1], cx, cy)

    def on_left_up(self, event):
        if self.drag_data["mode"]:
            self.drag_data["mode"] = None
            self.drag_data["item"] = None
            return

        if self.rect_start:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            x1, y1 = self.rect_start
            x2, y2 = cx, cy
            self.canvas.delete(self.current_rect_item)
            self.rect_start = None
            if abs(x2-x1) < 5: return
            self._add_annotation_from_coords(x1, y1, x2, y2)

    def _add_annotation_from_coords(self, x1, y1, x2, y2):
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        
        img_w, img_h = self.original_image.size
        
        real_x1 = x1 / self.zoom_level
        real_y1 = y1 / self.zoom_level
        real_x2 = x2 / self.zoom_level
        real_y2 = y2 / self.zoom_level
        
        w = real_x2 - real_x1
        h = real_y2 - real_y1
        cx = real_x1 + w/2
        cy = real_y1 + h/2
        
        self.annotations.append((self.current_class_id, cx/img_w, cy/img_h, w/img_w, h/img_h))
        
        cls_name = list(self.classes.keys())[list(self.classes.values()).index(self.current_class_id)]
        self.listbox_labels.insert(tk.END, f"{cls_name} ({int(w)}x{int(h)})")
        
        self.selected_annotation_index = len(self.annotations) - 1
        self.listbox_labels.selection_clear(0, tk.END)
        self.listbox_labels.selection_set(self.selected_annotation_index)
        self.redraw_boxes()

    # --- Helpers ---
    def select_class_by_index(self, index):
        names = list(self.classes.keys())
        if 0 <= index < len(names):
            name = names[index]
            self.combo_classes.set(name)
            self.current_class_id = self.classes[name]
            self._update_dimensions_from_config(name)

    def _update_class_combo(self):
        names = list(self.classes.keys())
        self.combo_classes['values'] = names
        if names:
            self.combo_classes.set(names[0])
            self.current_class_id = self.classes[names[0]]
            self._update_dimensions_from_config(names[0])

    def add_new_class(self):
        new_class = simpledialog.askstring("Yeni Sınıf", "Sınıf Adı:")
        if new_class and new_class not in self.classes:
            new_id = len(self.classes)
            self.classes[new_class] = new_id
            self._save_classes()
            self._update_class_combo()
            self.combo_classes.set(new_class)
            self.current_class_id = new_id
            self._update_dimensions_from_config(new_class)

    def on_class_selected(self, event):
        name = self.class_var.get()
        if name in self.classes:
            self.current_class_id = self.classes[name]
            self._update_dimensions_from_config(name)

    def on_listbox_select(self, event):
        sel = self.listbox_labels.curselection()
        if sel:
            self.selected_annotation_index = sel[0]
            self.redraw_boxes()

    def delete_selected_label(self):
        # Listbox önceliği
        sel = self.listbox_labels.curselection()
        if sel:
            idx = sel[0]
        elif self.selected_annotation_index != -1:
            idx = self.selected_annotation_index
        else:
            return
        self.delete_annotation_by_index(idx)

    def delete_annotation_by_index(self, idx):
        if 0 <= idx < len(self.annotations):
            del self.annotations[idx]
            self.listbox_labels.delete(idx)
            self.selected_annotation_index = -1
            self.hovered_annotation_index = -1
            self.redraw_boxes()
    
    def find_similar_context(self):
        if self.selected_annotation_index == -1: return
        idx = self.selected_annotation_index
        ann = self.annotations[idx]
        class_id, cx, cy, w, h = ann
        
        self.lbl_status.config(text="Aranıyor...", foreground="blue")
        self.root.update()
        
        img_w, img_h = self.original_image.size
        # Normals -> Canvas Coords for Template
        real_w = int(w * img_w)
        real_h = int(h * img_h)
        real_cx = int(cx * img_w)
        real_cy = int(cy * img_h)
        x1 = max(0, real_cx - real_w // 2)
        y1 = max(0, real_cy - real_h // 2)
        x2 = min(img_w, x1 + real_w)
        y2 = min(img_h, y1 + real_h)
        
        template = self.cv2_image[y1:y2, x1:x2]
        if template.size == 0: return

        img_gray = cv2.cvtColor(self.cv2_image, cv2.COLOR_BGR2GRAY)
        tmpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        res = cv2.matchTemplate(img_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.85)

        new_cnt = 0
        existing_pts = [(a[1]*img_w, a[2]*img_h) for a in self.annotations]
        
        for pt in zip(*loc[::-1]):
            cnx = pt[0] + real_w/2
            cny = pt[1] + real_h/2
            
            # Check dup
            is_dup = False
            for ex in existing_pts:
                if ((cnx-ex[0])**2 + (cny-ex[1])**2)**0.5 < 10:
                    is_dup = True; break
            if is_dup: continue
            
            existing_pts.append((cnx, cny))
            self.annotations.append((class_id, cnx/img_w, cny/img_h, real_w/img_w, real_h/img_h))
            cls_name = list(self.classes.keys())[list(self.classes.values()).index(class_id)]
            self.listbox_labels.insert(tk.END, f"{cls_name} (Auto)")
            new_cnt += 1
        
        self.redraw_boxes()
        self.lbl_status.config(text=f"Sonuç: {new_cnt} yeni")
        
    def _load_existing_labels(self):
        label_path = self.labels_dir / f"{self.pdf_name}_page_{self.current_page_index}.txt"
        if label_path.exists():
            with open(label_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        cx, cy, w, h = map(float, parts[1:5])
                        self.annotations.append((cls_id, cx, cy, w, h))
                        cname = "Unknown"
                        for k, v in self.classes.items():
                            if v == cls_id: cname = k
                        self.listbox_labels.insert(tk.END, cname)

    def save_page_data(self):
        if not self.original_image: return
        base_name = f"{self.pdf_name}_page_{self.current_page_index}"
        img_path = self.images_dir / f"{base_name}.jpg"
        self.original_image.save(img_path, quality=95)
        txt_path = self.labels_dir / f"{base_name}.txt"
        with open(txt_path, 'w') as f:
            for ann in self.annotations:
                f.write(f"{ann[0]} {ann[1]:.6f} {ann[2]:.6f} {ann[3]:.6f} {ann[4]:.6f}\n")
        self.lbl_status.config(text="KAYDEDİLDİ ✅", foreground="green")
        print(f"Saved: {base_name}")

    def on_zoom(self, event):
        if not self.original_image: return
        self.zoom_level *= 1.1 if event.delta > 0 else 0.9
        self.update_display()
    
    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
    
    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        
    def prev_page(self): self.load_page(self.current_page_index - 1)
    def next_page(self): self.load_page(self.current_page_index + 1)
    
    def show_context_menu(self, event):
         if self.selected_annotation_index != -1:
            self.context_menu.post(event.x_root, event.y_root)
    
    def delete_selected_context(self): self.delete_selected_label()

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartAnnotator(root)
    root.mainloop()
