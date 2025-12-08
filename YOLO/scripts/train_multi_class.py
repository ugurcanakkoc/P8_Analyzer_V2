from ultralytics import YOLO
import torch
import os
import shutil

def main():
    print("🚀 MULTI-CLASS YOLO EĞİTİMİ BAŞLATILIYOR...")

    # Cihaz Seçimi
    device = 0 if torch.cuda.is_available() else 'cpu'
    print(f"✅ Kullanılan Cihaz: {'GPU (CUDA)' if device == 0 else 'CPU'}")

    # Model Yükleme (Transfer Learning Öncelikli)
    pretrained_model = "../customers/troester/models/plc_model_backup.pt"
    if os.path.exists(pretrained_model):
        print(f"📦 Transfer Learning: {pretrained_model}")
        model = YOLO(pretrained_model)
    else:
        print("📦 Yeni Model: yolov8n.pt")
        model = YOLO('yolov8n.pt')

    # Eğitim Başlat
    results = model.train(
        data='../multi_class_data.yaml',
        epochs=50,
        imgsz=640,
        batch=8,
        device=device,
        patience=20,
        save=True,
        project='multi_class_training',
        name='terminal_contactor_v1',
        exist_ok=True,
        verbose=True
    )

    # Sonuçları Kaydet
    best_model = f"{results.save_dir}/weights/best.pt"
    target_dir = "../customers/troester/models"
    os.makedirs(target_dir, exist_ok=True)
    target_model = f"{target_dir}/plc_model.pt"

    shutil.copy(best_model, target_model)
    print(f"\n✅ Eğitim Tamamlandı! Model kaydedildi: {target_model}")

if __name__ == "__main__":
    main()
