"""
YOLO Training Script - GPU Accelerated
Röle tespiti için YOLOv8 eğitimi
"""

import torch
from ultralytics import YOLO
from pathlib import Path
import yaml
import shutil


def create_dataset_yaml():
    """YOLO için dataset.yaml oluştur"""
    data_dir = Path("c:/Users/Ugur Can/Desktop/P8_YOLO_Egitim/data/augmented")
    dataset_config = {
        'path': str(data_dir.absolute()),
        'train': 'images/train',
        'val': 'images/train',  # Validation için aynı set (küçük veri seti olduğu için)
        'names': {
            0: 'PLC',
            1: 'Terminal',
            2: 'Contactor',
            3: 'Other',
            4: 'Röle'
        }
    }
    yaml_path = data_dir / "dataset.yaml"
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(dataset_config, f, allow_unicode=True, sort_keys=False)
    print(f"✅ Dataset config oluşturuldu: {yaml_path}")
    return yaml_path


def train_yolo():
    """YOLO modelini eğit"""
    print("🚀 YOLO Eğitimi Başlatılıyor...\n")
    # GPU kontrolü
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"💻 Cihaz: {device}")
    if device == 'cuda':
        print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
        print(f"💾 GPU Bellek: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB\n")
    else:
        print("⚠️ GPU bulunamadı! CPU ile eğitim yapılacak (yavaş olabilir)\n")
    # Dataset config oluştur
    dataset_yaml = create_dataset_yaml()
    # Model seç (nano - hızlı eğitim için)
    model = YOLO('yolov8n.pt')
    print("\n📋 Eğitim Parametreleri:")
    print(f"  • Epochs: 100")
    print(f"  • Image Size: 640")
    print(f"  • Batch: 16 (GPU) or 8 (CPU)")
    print(f"  • Device: {device}")
    print(f"  • Patience: 20 (early stopping)\n")
    # Eğitim parametreleri
    train_args = {
        'data': str(dataset_yaml),
        'epochs': 100,
        'imgsz': 640,
        'batch': 16 if device == 'cuda' else 8,
        'device': device,
        'patience': 20,
        'save': True,
        'plots': True,
        'val': True,
        'verbose': True,
        'project': 'c:/Users/Ugur Can/Desktop/P8_YOLO_Egitim/runs',
        'name': 'role_detection',
        'exist_ok': True,
        # Optimization
        'optimizer': 'AdamW',
        'lr0': 0.001,
        'lrf': 0.01,
        'momentum': 0.937,
        'weight_decay': 0.0005,
        # Augmentation
        'hsv_h': 0.015,
        'hsv_s': 0.7,
        'hsv_v': 0.4,
        'degrees': 10,
        'translate': 0.1,
        'scale': 0.5,
        'flipud': 0.0,
        'fliplr': 0.5,
        'mosaic': 1.0,
    }
    print("🏋️ Eğitim başlıyor...\n")
    try:
        results = model.train(**train_args)
        print("\n✅ Eğitim tamamlandı!")
        print(f"📊 En iyi model: runs/role_detection/weights/best.pt")
        print(f"📈 Metrikler: runs/role_detection/\n")
        # Model testi
        print("🧪 Model test ediliyor...")
        metrics = model.val()
        print("\n📊 Test Sonuçları:")
        print(f"  • mAP50: {metrics.box.map50:.4f}")
        print(f"  • mAP50-95: {metrics.box.map:.4f}")
        print(f"  • Precision: {metrics.box.mp:.4f}")
        print(f"  • Recall: {metrics.box.mr:.4f}")
        return True
    except Exception as e:
        print(f"\n❌ Eğitim hatası: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = train_yolo()
    if success:
        print("\n🎉 Tüm işlemler başarıyla tamamlandı!")
        print("\n📝 Sonraki adımlar:")
        print("1. Model performansını kontrol et: runs/role_detection/")
        print("2. En iyi modeli kullan: runs/role_detection/weights/best.pt")
        print("3. Gerçek test verileriyle dene")
    else:
        print("\n⚠️ Eğitim başarısız oldu. Lütfen hataları kontrol edin.")
