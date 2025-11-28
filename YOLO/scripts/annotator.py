"""
PDF YOLO Annotator Tool v2.0 (Turbo Mode)
Hızlı veri etiketleme için Zoom, Pan ve Kısayol özellikleri eklendi.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw
import pymupdf
import os
from pathlib import Path

class PDFYOLOAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("🏷️ PDF YOLO Annotator v2.0 (Turbo Mode)")
        self.root.geometry("1400x900")
        
        # Klasör Yapısı
        self.base_dir = Path("..") / "data" / "annotated"
        self.images_dir = self.base_dir / "images" / "train"
        self.labels_dir = self.base_dir / "labels" / "train"
        self.classes_file = self.base_dir / "classes.txt"
        
        self._setup_directories()
        
        # Durum Değişkenleri
        self.classes = self._load_classes() # {name: id}
        self.current_class_id = 0
        self.pdf_doc = None
        self.current_page_index = 0
        self.rect_start = None
        self.current_rect = None
        self.annotations = [] # [(class_id, x_norm, y_norm, w_norm, h_norm)]
        
        # Görüntü ve Zoom
        self.original_image = None # Yüksek çözünürlüklü ham resim
        self.display_image = None  # Ekranda gösterilen (resize edilmiş)
        self.tk_image = None
        self.zoom_level = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.pan_start = None
        
        self._build_ui()
        self._bind_shortcuts()
        
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

    def _build_ui(self):
        # Sol Panel (Canvas)
        self.left_panel = ttk.Frame(self.root)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar'lar (Otomatik gizlenir ama pan için gerekli altyapı)
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
        self.canvas.bind("<Button-3>", self.cancel_draw) # Sağ tık iptal
        
        # Zoom & Pan Olayları
        self.canvas.bind("<MouseWheel>", self.on_zoom) # Windows
        self.canvas.bind("<ButtonPress-2>", self.start_pan) # Orta tuş
        self.canvas.bind("<B2-Motion>", self.do_pan)
        
        # Sağ Panel (Kontroller)
        self.right_panel = ttk.Frame(self.root, width=300)
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
        
        # Sınıf Seçimi
        ttk.Label(self.right_panel, text="Sınıf (Kısayol: 1, 2, 3...)", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        
        self.class_var = tk.StringVar()
        self.combo_classes = ttk.Combobox(self.right_panel, textvariable=self.class_var, state="readonly")
        self.combo_classes.pack(fill=tk.X)
        self.combo_classes.bind("<<ComboboxSelected>>", self.on_class_selected)
        
        # Yeni Sınıf Ekle
        ttk.Button(self.right_panel, text="➕ Yeni Sınıf Ekle", command=self.add_new_class).pack(fill=tk.X, pady=5)
        
        # Listbox (Mevcut Etiketler)
        ttk.Label(self.right_panel, text="Sayfadaki Etiketler:", font=("Arial", 10, "bold")).pack(pady=(20, 5))
        self.listbox_labels = tk.Listbox(self.right_panel, height=10)
        self.listbox_labels.pack(fill=tk.X)
        
        ttk.Button(self.right_panel, text="🗑️ Seçileni Sil (Del)", command=self.delete_selected_label).pack(fill=tk.X, pady=5)
        
        # Kaydet
        ttk.Separator(self.right_panel, orient='horizontal').pack(fill=tk.X, pady=20)
        self.btn_save = ttk.Button(self.right_panel, text="💾 KAYDET (S)", command=self.save_page_data, state=tk.DISABLED)
        self.btn_save.pack(fill=tk.X, ipady=10)
        
        # Kısayol Bilgisi
        info_text = """
        Kısayollar:
        Mouse Teker: Zoom
        Orta Tuş: Pan (Kaydır)
        1-9: Sınıf Seç
        A / D: Önceki / Sonraki Sayfa
        S: Kaydet
        Del: Sil
        """
        ttk.Label(self.right_panel, text=info_text, font=("Arial", 8), justify=tk.LEFT).pack(side=tk.BOTTOM, pady=10)
        
        self._update_class_combo()

    def _bind_shortcuts(self):
        self.root.bind("<Right>", lambda e: self.next_page())
        self.root.bind("<d>", lambda e: self.next_page())
        self.root.bind("<Left>", lambda e: self.prev_page())
        self.root.bind("<a>", lambda e: self.prev_page())
        self.root.bind("<s>", lambda e: self.save_page_data())
        self.root.bind("<Delete>", lambda e: self.delete_selected_label())
        
        # Sayı tuşları (1-9)
        for i in range(1, 10):
            self.root.bind(str(i), lambda e, idx=i-1: self.select_class_by_index(idx))

    def select_class_by_index(self, index):
        names = list(self.classes.keys())
        if 0 <= index < len(names):
            name = names[index]
            self.combo_classes.set(name)
            self.current_class_id = self.classes[name]
            self._show_toast(f"Sınıf Seçildi: {name}")

    def _show_toast(self, message):
        # Geçici bilgi mesajı (Canvas üzerinde)
        toast = self.canvas.create_text(self.canvas.winfo_width()/2, 30, text=message, fill="yellow", font=("Arial", 20, "bold"))
        self.root.after(1000, lambda: self.canvas.delete(toast))

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
        if not file_path: return
        
        self.pdf_doc = pymupdf.open(file_path)
        self.pdf_name = Path(file_path).stem
        self.current_page_index = 0
        self.load_page(0)

    def load_page(self, index):
        if not self.pdf_doc: return
        if index < 0 or index >= len(self.pdf_doc): return
        
        self.current_page_index = index
        self.lbl_page.config(text=f"{index + 1}/{len(self.pdf_doc)}")
        
        # Yüksek Kaliteli Render (300 DPI civarı)
        page = self.pdf_doc[index]
        zoom_matrix = pymupdf.Matrix(3, 3) 
        pix = page.get_pixmap(matrix=zoom_matrix)
        self.original_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        
        # Reset View
        self.zoom_level = 1.0
        # Ekrana sığacak şekilde başlangıç zoom'u ayarla
        screen_h = self.root.winfo_height() - 100
        if self.original_image.height > screen_h:
            self.zoom_level = screen_h / self.original_image.height
            
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        
        self.annotations = []
        self.listbox_labels.delete(0, tk.END)
        self.btn_save.config(state=tk.NORMAL)
        
        self._check_existing_labels()
        self.update_display()

    def update_display(self):
        if not self.original_image: return
        
        # Resize
        new_w = int(self.original_image.width * self.zoom_level)
        new_h = int(self.original_image.height * self.zoom_level)
        
        # Çok büyük/küçük olmasını engelle
        if new_w < 100: new_w = 100
        if new_h < 100: new_h = 100
        
        self.display_image = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(self.display_image)
        
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        
        # Kutuları Çiz
        self.redraw_boxes()

    def redraw_boxes(self):
        self.canvas.delete("box")
        img_w, img_h = self.original_image.size
        
        for ann in self.annotations:
            cls_id, cx, cy, w, h = ann
            
            # Normalize -> Orijinal Piksel
            real_w = w * img_w
            real_h = h * img_h
            real_cx = cx * img_w
            real_cy = cy * img_h
            
            x1 = real_cx - real_w/2
            y1 = real_cy - real_h/2
            x2 = real_cx + real_w/2
            y2 = real_cy + real_h/2
            
            # Orijinal Piksel -> Zoomlu Ekran
            sx1 = x1 * self.zoom_level
            sy1 = y1 * self.zoom_level
            sx2 = x2 * self.zoom_level
            sy2 = y2 * self.zoom_level
            
            color = self.get_class_color(cls_id)
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=color, width=2, tags="box")

    def get_class_color(self, cls_id):
        colors = ["red", "blue", "green", "yellow", "cyan", "magenta", "orange"]
        return colors[cls_id % len(colors)]

    def _check_existing_labels(self):
        label_path = self.labels_dir / f"{self.pdf_name}_page_{self.current_page_index}.txt"
        if label_path.exists():
            with open(label_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cls_id = int(parts[0])
                        cx, cy, w, h = map(float, parts[1:])
                        self.annotations.append((cls_id, cx, cy, w, h))
                        
                        cls_name = next((k for k, v in self.classes.items() if v == cls_id), str(cls_id))
                        self.listbox_labels.insert(tk.END, f"{cls_name}")

    def prev_page(self):
        self.load_page(self.current_page_index - 1)

    def next_page(self):
        self.load_page(self.current_page_index + 1)

    # --- Zoom & Pan ---
    def on_zoom(self, event):
        if not self.original_image: return
        
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_level *= factor
        self.update_display()

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    # --- Çizim ---
    def on_mouse_down(self, event):
        # Canvas koordinatlarını al (Scroll/Pan durumunu dikkate alarak)
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        self.rect_start = (canvas_x, canvas_y)
        self.current_rect = self.canvas.create_rectangle(canvas_x, canvas_y, canvas_x, canvas_y, outline="white", width=2, dash=(4, 4))

    def on_mouse_drag(self, event):
        if self.rect_start:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.current_rect, self.rect_start[0], self.rect_start[1], canvas_x, canvas_y)

    def on_mouse_up(self, event):
        if not self.rect_start: return
        
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

    def cancel_draw(self, event):
        if self.current_rect:
            self.canvas.delete(self.current_rect)
            self.rect_start = None

    def _add_annotation(self, x1, y1, x2, y2):
        # Ekran koordinatlarından -> Orijinal Resim Koordinatlarına
        real_x1 = x1 / self.zoom_level
        real_y1 = y1 / self.zoom_level
        real_x2 = x2 / self.zoom_level
        real_y2 = y2 / self.zoom_level
        
        img_w, img_h = self.original_image.size
        
        # Normalize et
        cx = ((real_x1 + real_x2) / 2) / img_w
        cy = ((real_y1 + real_y2) / 2) / img_h
        w = (real_x2 - real_x1) / img_w
        h = (real_y2 - real_y1) / img_h
        
        self.annotations.append((self.current_class_id, cx, cy, w, h))
        
        cls_name = self.class_var.get()
        self.listbox_labels.insert(tk.END, f"{cls_name}")

    def delete_selected_label(self):
        sel = self.listbox_labels.curselection()
        if not sel: return
        
        idx = sel[0]
        self.listbox_labels.delete(idx)
        del self.annotations[idx]
        self.redraw_boxes()

    def save_page_data(self):
        if not self.original_image: return
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
        
        self._show_toast("KAYDEDİLDİ! ✅")
        self.btn_save.config(text="✅ KAYDEDİLDİ!", state=tk.DISABLED)
        self.root.after(1000, lambda: self.btn_save.config(text="💾 KAYDET (S)", state=tk.NORMAL))
        print(f"Kaydedildi: {base_name}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFYOLOAnnotator(root)
    root.mainloop()
