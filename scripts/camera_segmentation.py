import os
import cv2
import numpy as np
import argparse
from skimage.feature import hog
import joblib

IMG_SIZE = (128, 128)


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


def segment_product(frame):
    """Ürün bölgesini segmentasyon ile çıkart"""
    # Gri tonlamaya çevir
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Blur
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Dilation & erosion
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    edges = cv2.dilate(edges, kernel, iterations=2)
    edges = cv2.erode(edges, kernel, iterations=1)
    
    # Kontür bul
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    boxes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        # Makul boyuttaki nesneler
        if 3000 < area < 150000:
            x, y, w, h = cv2.boundingRect(contour)
            # Çok dar veya çok geniş olanları atla
            aspect_ratio = w / h if h > 0 else 0
            if 0.3 < aspect_ratio < 3.0:
                boxes.append((x, y, w, h, area))
    
    # En büyük nesneyi seç
    if boxes:
        boxes.sort(key=lambda x: x[4], reverse=True)
        return boxes[0][:4]
    
    return None


def extract_hog(img_array):
    """HOG özelliklerini çıkart (iyileştirilmiş)"""
    try:
        if img_array.size == 0:
            return None
            
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
        
        # Kontrastı artır (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Gauss blur (denoising)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Resize
        gray_resized = cv2.resize(gray, IMG_SIZE)
        gray_resized = gray_resized.astype(np.float32) / 255.0
        
        # HOG - daha detaylı parametreler
        feat = hog(gray_resized, 
                   pixels_per_cell=(8, 8),  # Daha küçük hücreler
                   cells_per_block=(2, 2), 
                   feature_vector=True,
                   channel_axis=None,
                   block_norm='L2-Hys')
        
        return feat
    except Exception as e:
        return None


def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    
    # Modeli yükle
    model_path = os.path.join(split_root, 'hog_logreg.joblib')
    if not os.path.isfile(model_path):
        print(f"Model bulunamadı: {model_path}")
        return
    
    print("Model yükleniyor...")
    model_data = joblib.load(model_path)
    clf = model_data.get('model')
    le = model_data.get('label_encoder')
    
    if clf is None or le is None:
        print("Model yüklenemedi")
        return
    
    print(f"Sınıflar: {list(le.classes_)}")
    print("\nKamera başlatılıyor...")
    print("Ürünü kameraya doğru yöneltin")
    print("Çıkış: ESC veya 'q'\n")
    
    cap = cv2.VideoCapture(args.camera_id)
    if not cap.isOpened():
        print("Kamera açılamadı!")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    frame_count = 0
    predictions_history = []
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            display = frame.copy()
            
            # Ürünü segmentasyon ile çıkart
            product_box = segment_product(frame)
            
            if product_box is not None:
                x, y, w, h = product_box
                
                # Padding ekle
                pad = 20
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(frame.shape[1], x + w + pad)
                y2 = min(frame.shape[0], y + h + pad)
                
                roi = frame[y1:y2, x1:x2]
                
                if roi.size > 0:
                    # HOG çıkart ve tahmin yap
                    feat = extract_hog(roi)
                    
                    if feat is not None:
                        try:
                            pred_idx = clf.predict([feat])[0]
                            pred_label = le.inverse_transform([pred_idx])[0]
                            confidence = clf.predict_proba([feat])[0][pred_idx]
                            
                            # Geçmiş tahmini güncelle (moving average)
                            predictions_history.append((pred_label, confidence))
                            if len(predictions_history) > 10:
                                predictions_history.pop(0)
                            
                            # En sık tahmin
                            from collections import Counter
                            pred_counts = Counter([p[0] for p in predictions_history])
                            most_common_pred = pred_counts.most_common(1)[0][0]
                            avg_confidence = np.mean([p[1] for p in predictions_history 
                                                     if p[0] == most_common_pred])
                            
                            # Bounding box çiz
                            color = (0, 255, 0) if avg_confidence > 0.5 else (0, 165, 255)
                            cv2.rectangle(display, (x1, y1), (x2, y2), color, 3)
                            
                            # Ana tahmin
                            text = f"{most_common_pred}: {avg_confidence:.0%}"
                            cv2.putText(display, text, (x1, y1-20), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
                            
                            # Tüm tahminleri göster
                            cv2.putText(display, "Tahminler:", (10, 30), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                            
                            for i, (lbl, conf) in enumerate(clf.predict_proba([feat])[0].argsort()[::-1][:3]):
                                class_label = le.inverse_transform([lbl])[0]
                                class_conf = clf.predict_proba([feat])[0][lbl]
                                text = f"  {i+1}. {class_label}: {class_conf:.0%}"
                                color_text = (0, 255, 0) if i == 0 else (200, 200, 200)
                                cv2.putText(display, text, (10, 60+i*30), 
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_text, 1)
                        
                        except Exception as e:
                            cv2.putText(display, f"Hata: {str(e)[:30]}", (10, 60), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
            else:
                cv2.putText(display, "Urun algılanmıyor", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(display, "Urunun tamamını kameraya yon", (10, 100), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            
            cv2.putText(display, f"Frame: {frame_count}", (10, display.shape[0]-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            cv2.imshow('Urun Siniflandirma - Segmentasyon', display)
            
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
