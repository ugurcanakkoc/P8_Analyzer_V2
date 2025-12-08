
from ultralytics import YOLO
import torch
import os
import shutil
import yaml
from pathlib import Path

def setup_training_data(base_dir):
    """
    Eğitim için gerekli YAML dosyasını otomatik oluşturur.
    classes.txt dosyasındaki güncel sınıf listesini kullanır.
    """
    base_dir = Path(base_dir).resolve()
    
    # 1. Sınıf Listesini Oku
    classes_file = base_dir / "classes.txt"
    if not classes_file.exists():
        print(f"❌ '{classes_file}' bulunamadı! Önce annotator.py ile etiket ekleyin.")
        return None
        
    with open(classes_file, 'r') as f:
        class_names = [line.strip() for line in f.readlines() if line.strip()]
        
    if not class_names:
        print("❌ Sınıf listesi boş! classes.txt dosyasını kontrol edin.")
        return None

    # 2. YAML İçeriği Hazırla (Pathler mutlak olmalı ki YOLO hata vermesin)
    data_yaml = {
        'path': str(base_dir), # Dataset root dir
        'train': 'images/train',
        'val': 'images/train', # Şimdilik val için de train kullanıyoruz (Veri azsa)
        'names': {i: name for i, name in enumerate(class_names)}
    }
    
    yaml_path = base_dir / "dataset.yaml"
    with open(yaml_path, 'w') as f:
        yaml.dump(data_yaml, f, sort_keys=False)
        
    print(f"✅ Dataset YAML oluşturuldu: {yaml_path}")
    print(f"📋 Sınıflar ({len(class_names)}): {class_names}")
    
    return yaml_path

def train():
    # Klasör Ayarları
    script_dir = Path(__file__).resolve().parent
    yolo_root = script_dir.parent
    data_dir = yolo_root / "data"
    runs_dir = yolo_root / "runs"
    
    print("\n🚀 YOLO EĞİTİM YÖNETİCİSİ V2.0")
    print("=================================")
    
    # Dataset Hazırlığı
    yaml_path = setup_training_data(data_dir)
    if not yaml_path: return

    # Cihaz Seçimi
    device = 0 if torch.cuda.is_available() else 'cpu'
    print(f"⚙️  Donanım: {'GPU (CUDA) 🚀' if device == 0 else 'CPU (Yavaş)'}")

    # Model Seçimi
    # Eğer daha önce eğitilmiş 'best.pt' varsa ondan devam edelim (Transfer Learning)
    last_best = runs_dir / "detect" / "train" / "weights" / "best.pt"
    if last_best.exists():
        print(f"📦 Önceki model bulundu, eğitim devam ediyor: {last_best}")
        model_path = str(last_best)
    else:
        print("📦 Sıfırdan eğitim başlatılıyor (yolo11n.pt)") # YOLOv8/v11 nano
        model_path = "yolo11n.pt" 
        
    try:
        model = YOLO(model_path)
    except:
        print("⚠️ Model yüklenemedi, 'yolov8n.pt' deneniyor...")
        model = YOLO("yolov8n.pt")

    # Eğitim Parametreleri
    print("\n🏋️ Eğitim Başlıyor...")
    results = model.train(
        data=str(yaml_path),
        epochs=100,            # 100 epoch ideal
        imgsz=640,            # Resim boyutu
        batch=16,              # Batch size (VRAM yetmezse düşebilir: 8, 4)
        patience=20,          # 20 epoch boyunca iyileşme olmazsa dur
        device=device,
        project=str(runs_dir / "detect"),
        name='train',
        exist_ok=True,        # Üzerine yaz
        verbose=True
    )
    
    # Sonuç
    final_model_path = runs_dir / "detect" / "train" / "weights" / "best.pt"
    print(f"\n✅ EĞİTİM TAMAMLANDI!")
    print(f"💾 Yeni Model Kaydedildi: {final_model_path}")
    print("👉 Şimdi smart_annotator.py uygulamasında 'Model Yükle' diyerek bu dosyayı seçebilirsin.")

if __name__ == "__main__":
    train()
