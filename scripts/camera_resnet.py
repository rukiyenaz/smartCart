import os
import cv2
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import numpy as np
import argparse
import joblib
from collections import deque

IMG_SIZE = 224


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory',
    )
    parser.add_argument(
        '--camera-id',
        type=int,
        default=0,
        help='Camera ID',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    
    model_path = os.path.join(split_root, 'resnet18_model.pth')
    le_path = os.path.join(split_root, 'label_encoder.joblib')
    
    if not os.path.isfile(model_path):
        print(f"Model bulunamadı: {model_path}")
        print("Lütfen önce: python scripts/train_resnet.py --dataset-dir migros_dataset_merged")
        return
    
    if not os.path.isfile(le_path):
        print(f"Label encoder bulunamadı: {le_path}")
        return
    
    print("ResNet18 modeli yükleniyor...")
    
    # Cihaz
    device = torch.device('cpu')
    
    # Model yükle
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    model = models.resnet18()
    num_classes = len(checkpoint['class_names'])
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    model.load_state_dict(checkpoint['model_state'])
    model = model.to(device)
    model.eval()
    
    # LabelEncoder yükle
    le = joblib.load(le_path)
    
    print(f"Sınıflar: {list(le.classes_)}")
    print("\n" + "="*60)
    print("URUN SINIFLANDIRMA - ResNet18 CNN")
    print("="*60)
    print("Kamerayı açıyorum...")
    print("Ürünü sarı dikdörtgene yönelt")
    print("Çıkış: ESC veya 'q'\n")
    
    cap = cv2.VideoCapture(args.camera_id)
    if not cap.isOpened():
        print("Kamera açılamadı!")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Transform
    transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
    frame_count = 0
    predictions_history = deque(maxlen=15)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            h, w = frame.shape[:2]
            display = frame.copy()
            
            # ROI - merkez kare
            center_x, center_y = w // 2, h // 2
            roi_size = 280
            
            x1 = max(0, center_x - roi_size // 2)
            y1 = max(0, center_y - roi_size // 2)
            x2 = min(w, center_x + roi_size // 2)
            y2 = min(h, center_y + roi_size // 2)
            
            roi = frame[y1:y2, x1:x2]
            
            # Dikdörtgeni goster
            cv2.rectangle(display, (x1, y1), (x2, y2), (255, 255, 0), 3)
            cv2.putText(display, "URUN BURAYA", (x1, y1-15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            if roi.size > 0 and roi.shape[0] > 0 and roi.shape[1] > 0:
                try:
                    # PIL'e çevir
                    roi_pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
                    
                    # Transform
                    roi_tensor = transform(roi_pil).unsqueeze(0).to(device)
                    
                    # Tahmin yap
                    with torch.no_grad():
                        output = model(roi_tensor)
                        probabilities = torch.softmax(output, dim=1)[0]
                        pred_idx = torch.argmax(probabilities).item()
                        pred_prob = probabilities[pred_idx].item()
                        pred_label = le.classes_[pred_idx]
                    
                    # Geçmiş ekle
                    predictions_history.append((str(pred_label), pred_prob))
                    
                    # Ortalama tahmin
                    from collections import Counter
                    pred_counts = Counter([p[0] for p in predictions_history])
                    most_common = pred_counts.most_common(1)[0][0]
                    
                    avg_conf = np.mean([p[1] for p in predictions_history if p[0] == most_common])
                    
                    # Renk
                    if avg_conf > 0.7:
                        color = (0, 255, 0)  # Yeşil
                    elif avg_conf > 0.5:
                        color = (0, 255, 255)  # Sarı
                    else:
                        color = (0, 165, 255)  # Turuncu
                    
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 4)
                    
                    # Ana tahmin
                    main_text = f"{most_common.upper()}: {avg_conf:.0%}"
                    cv2.putText(display, main_text, (x1, y1-50), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1.3, color, 3)
                    
                    # Top 3
                    y_offset = 50
                    cv2.putText(display, "En Iyi 3:", (20, y_offset), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
                    
                    sorted_probs, sorted_indices = torch.sort(probabilities, descending=True)
                    
                    for rank in range(min(3, len(le.classes_))):
                        class_label = le.classes_[sorted_indices[rank].item()]
                        class_prob = sorted_probs[rank].item()
                        text = f"{rank+1}. {class_label}: {class_prob:.0%}"
                        y_pos = y_offset + 35 * (rank + 1)
                        if y_pos < h - 20:
                            c = (0, 255, 0) if rank == 0 else (180, 180, 180)
                            cv2.putText(display, text, (20, y_pos), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.85, c, 2)
                
                except Exception as e:
                    cv2.putText(display, f"Hata: {str(e)[:40]}", (20, 100), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            cv2.putText(display, f"Frame: {frame_count}", (10, h-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            cv2.imshow('ResNet18 Urun Siniflandirma', display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\nKapatıldı.")


if __name__ == '__main__':
    main()
