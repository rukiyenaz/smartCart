import os
import cv2
import numpy as np
import argparse
from skimage.feature import hog
import joblib

IMG_SIZE = (128, 128)
WINDOW_SIZE = 200  # Pencere boyutu


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


def extract_hog(img_array):
    """HOG özelliklerini çıkart"""
    try:
        if img_array.size == 0:
            return None
            
        # Gri tonlamaya çevir
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
        
        # Kontrastı artır (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # 128x128'e resize et
        gray_resized = cv2.resize(gray, IMG_SIZE)
        gray_resized = gray_resized.astype(np.float32) / 255.0
        
        # HOG hesapla
        feat = hog(gray_resized, pixels_per_cell=(16, 16), cells_per_block=(2, 2), 
                   feature_vector=True, channel_axis=None)
        return feat
    except Exception as e:
        return None


def predict_window(clf, le, roi):
    """Bir pencere için tahmin yap"""
    try:
        feat = extract_hog(roi)
        if feat is None:
            return None, 0.0
        
        pred_idx = clf.predict([feat])[0]
        pred_label = le.inverse_transform([pred_idx])[0]
        confidence = clf.predict_proba([feat])[0][pred_idx]
        
        return pred_label, confidence
    except:
        return None, 0.0


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
    print("Kameranızı ürüne doğru yöneltin")
    print("ESC veya 'q' ile çıkış\n")
    
    cap = cv2.VideoCapture(args.camera_id)
    if not cap.isOpened():
        print("Kamera açılamadı!")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    frame_count = 0
    best_prediction = None
    best_confidence = 0.0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            h, w = frame.shape[:2]
            
            # Orta bölgeden sliding window ile tarama
            results = []
            step = 100
            
            for y in range(0, h - WINDOW_SIZE, step):
                for x in range(0, w - WINDOW_SIZE, step):
                    roi = frame[y:y+WINDOW_SIZE, x:x+WINDOW_SIZE]
                    
                    label, conf = predict_window(clf, le, roi)
                    if label is not None and conf > 0.3:  # Güven eşiği
                        results.append((label, conf, (x, y)))
            
            # En iyi sonucu seç
            if results:
                results.sort(key=lambda x: x[1], reverse=True)
                best_prediction, best_confidence, (bx, by) = results[0]
                
                # En iyi bölgeyi çiz
                color = (0, 255, 0) if best_confidence > 0.5 else (0, 165, 255)
                cv2.rectangle(frame, (bx, by), (bx+WINDOW_SIZE, by+WINDOW_SIZE), color, 3)
                
                # Etiketi yaz
                label_text = f"{best_prediction}: {best_confidence:.0%}"
                cv2.putText(frame, label_text, (bx, by-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                
                # Diğer tahminleri göster
                cv2.putText(frame, "En Iyi Tahminler:", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                
                for i, (lbl, conf, _) in enumerate(results[:3]):
                    text = f"{i+1}. {lbl}: {conf:.0%}"
                    cv2.putText(frame, text, (10, 60+i*25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            else:
                cv2.putText(frame, "Tahmin yapilmiyor...", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            
            # Bilgi göster
            cv2.putText(frame, f"Frame: {frame_count}", (10, frame.shape[0]-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            cv2.imshow('Urun Tahmin - Sliding Window', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 27 = ESC
                break
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\nKapat─▒ld─▒.")


if __name__ == '__main__':
    main()
