import os
import cv2
import numpy as np
import argparse
from skimage import color, transform
from skimage.feature import hog
import joblib

IMG_SIZE = (128, 128)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing processed split metadata',
    )
    parser.add_argument(
        '--camera-id',
        type=int,
        default=0,
        help='Camera ID (0 for default camera)',
    )
    return parser.parse_args()


def extract_hog(img_array):
    """HOG özelliklerini çıkart"""
    try:
        # Gri tonlamaya çevir
        if len(img_array.shape) == 3:
            img_gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img_array
        
        # CLAHE (Contrast Limited Adaptive Histogram Equalization) uygula
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img_gray = clahe.apply(img_gray)
        
        # Boyutlandır
        img_resized = cv2.resize(img_gray, IMG_SIZE)
        img_resized = img_resized.astype(np.float32) / 255.0
        
        # HOG özelliklerini çıkart
        feat = hog(img_resized, pixels_per_cell=(16, 16), cells_per_block=(2, 2), 
                   feature_vector=True, channel_axis=None)
        return feat
    except Exception as e:
        return None


def detect_objects(frame):
    """Nesneleri algıla ve bounding box'lar döndür"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Blur uygula
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Adaptif threshold
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    
    # Morfolojik işlemler
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    # Kontür bul
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    boxes = []
    for contour in contours:
        area = cv2.contourArea(contour)
        # Çok küçük veya çok büyük kontürleri atla
        if 5000 < area < 100000:
            x, y, w, h = cv2.boundingRect(contour)
            boxes.append((x, y, w, h))
    
    return boxes


def get_prediction_confidence(clf, features, class_idx):
    """Tahmin güvenini al"""
    try:
        probs = clf.predict_proba([features])[0]
        return probs[class_idx]
    except:
        return 0.0


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
    
    print(f"Model yükleniyor: {model_path}")
    model_data = joblib.load(model_path)
    clf = model_data.get('model')
    le = model_data.get('label_encoder')
    
    if clf is None or le is None:
        print("Model veya label encoder yüklenemedi")
        return
    
    print(f"Sınıflar: {list(le.classes_)}")
    print("\nKamera başlatılıyor...")
    print("Kamerayla tahmin sistem aktif")
    print("Nesneleri algılamayı denemeye başladı")
    print("Çıkmak için 'q' tuşuna basın.\n")
    
    # Kamerayı aç
    cap = cv2.VideoCapture(args.camera_id)
    
    if not cap.isOpened():
        print("Kamera açılamadı!")
        return
    
    # Kamera özelliklerini ayarla
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Frame okunamadı!")
                break
            
            frame_count += 1
            
            # Nesneleri algıla
            boxes = detect_objects(frame)
            
            # Her tespit edilen nesne için tahmin yap
            if len(boxes) > 0:
                for (x, y, w, h) in boxes:
                    # Nesne bölgesini çıkart
                    roi = frame[max(0, y):min(frame.shape[0], y+h), 
                               max(0, x):min(frame.shape[1], x+w)]
                    
                    if roi.size > 0:
                        try:
                            features = extract_hog(roi)
                            if features is not None:
                                pred_class_idx = clf.predict([features])[0]
                                pred_label = le.inverse_transform([pred_class_idx])[0]
                                confidence = get_prediction_confidence(clf, features, pred_class_idx)
                                
                                # Bounding box çiz
                                color = (0, 255, 0) if confidence > 0.5 else (0, 165, 255)
                                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                                
                                # Etiketi yazı
                                text = f"{pred_label}: {confidence:.0%}"
                                cv2.putText(frame, text, (x, y-10), 
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        except Exception as e:
                            pass
            else:
                # Nesne algılanmadı mesajı
                cv2.putText(frame, "Nesne algılanmıyor", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Frame sayısını göster
            cv2.putText(frame, f"Frame: {frame_count}", (10, frame.shape[0]-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            # Talimatları göster
            cv2.putText(frame, "Cikmak: q | Nesneleri degistir", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            # Frame'i göster
            cv2.imshow('Urun Tahmin - Nesneleri Algila', frame)
            
            # 'q' tuşu kontrolü
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\nKamera kapatılıyor...")
                break
    
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("İşlem tamamlandı!")


if __name__ == '__main__':
    main()
