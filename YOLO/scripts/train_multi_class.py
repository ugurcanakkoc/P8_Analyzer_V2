"""
Multi-Class YOLO Eğitimi (GPU/CUDA)
PLC + Terminal + Contactor sınıflarını öğrenir.
"""

from ultralytics import YOLO
import torch
import os

def main():
    print("="*60)
    print("🚀 MULTI-CLASS YOLO EĞİTİMİ (GPU)")
    print("="*60)

    # GPU Kontrolü
    if torch.cuda.is_available():
        print(f"✅ GPU Bulundu: {torch.cuda.get_device_name(0)}")
        print(f"   CUDA Versiyonu: {torch.version.cuda}")
        device = 0  # GPU
    else:
        print("⚠️ GPU bulunamadı, CPU kullanılacak.")
        device = 'cpu'

    # Model Yükle (Transfer Learning)
    print("\n📦 Model yükleniyor...")

    # Eğer önceki PLC modeliniz varsa onu kullan (Transfer Learning)
    pretrained_model = "../customers/troester/models/plc_model_backup.pt"

    if os.path.exists(pretrained_model):
        print(f"   Önceki model bulundu: {pretrained_model}")
        print("   Transfer Learning uygulanacak (Daha hızlı öğrenme)")
        model = YOLO(pretrained_model)
    else:
        print("   YOLOv8n (Nano) sıfırdan başlatılıyor...")
        model = YOLO('yolov8n.pt')

    # Eğitim Parametreleri
    print("\n⚙️ Eğitim Parametreleri:")

    EPOCHS = 50  # Hızlı test için azaltıldı
    IMG_SIZE = 640
    BATCH_SIZE = 8  # GPU belleği için azaltıldı

    print(f"   Epochs: {EPOCHS}")
    print(f"   Image Size: {IMG_SIZE}")
    print(f"   Batch Size: {BATCH_SIZE}")
    print(f"   Device: {'GPU (CUDA)' if device == 0 else 'CPU'}")

    # Eğitim
    print("\n🎯 Eğitim başlıyor...\n")

    results = model.train(
        data='../multi_class_data.yaml',
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device=device,
        
        # Optimizasyon
        patience=20,           # Early stopping (20 epoch iyileşme yoksa dur)
        save=True,
        save_period=10,        # Her 10 epoch'ta checkpoint kaydet
        
        # Augmentation (Eğer zaten augmente ettiyseniz azaltın)
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10,
        translate=0.1,
        scale=0.5,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        
        # Performans
        workers=8,
        project='multi_class_training',
        name='terminal_contactor_v1',
        exist_ok=True,
        verbose=True
    )

    print("\n" + "="*60)
    print("✅ EĞİTİM TAMAMLANDI!")
    print("="*60)

    # Sonuçlar
    print(f"\n📊 En İyi Model: {results.save_dir}/weights/best.pt")
    print(f"📈 Metrikler:")
    print(f"   mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    print(f"   mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A')}")

    # Modeli Müşteri Klasörüne Kopyala
    import shutil
    best_model = f"{results.save_dir}/weights/best.pt"
    target_model = "../customers/troester/models/plc_model.pt"

    print(f"\n💾 Model kaydediliyor: {target_model}")
    shutil.copy(best_model, target_model)

    print("\n🎉 Yeni model hazır! Artık PLC, Terminal ve Contactor tespit edebilir.")

if __name__ == "__main__":
    main()
