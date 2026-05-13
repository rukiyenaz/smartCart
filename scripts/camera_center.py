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


def extract_hog(img_array):
    """HOG özelliklerini çıkart"""
    try:
        if img_array.size == 0:
            return None
            
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
        
        # Kontrastı artır
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Resize
        gray_resized = cv2.resize(gray, IMG_SIZE)
        gray_resized = gray_resized.astype(np.float32) / 255.0
        
        # HOG
        feat = hog(gray_resized, 
                   pixels_per_cell=(16, 16),
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
    
    print(f"Siniflar: {list(le.classes_)}")
    print("\nKamera ACILIYOR...")
    print("Urunu kameraya dogru YONELT")
    print("Cikmak: ESC veya 'q'\n")
    
    cap = cv2.VideoCapture(args.camera_id)
    if not cap.isOpened():
        print("Kamera acilamadi!")
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
            h, w = frame.shape[:2]
            display = frame.copy()
            
            # MERKEZ BOLGEYI KULLAN (orta 50% alanı)
            center_x, center_y = w // 2, h // 2
            roi_size = 280  # Kare BOI boyutu
            
            x1 = max(0, center_x - roi_size // 2)
            y1 = max(0, center_y - roi_size // 2)
            x2 = min(w, center_x + roi_size // 2)
            y2 = min(h, center_y + roi_size // 2)
            
            roi = frame[y1:y2, x1:x2]
            
            # Dikdortgeni goster
            cv2.rectangle(display, (x1, y1), (x2, y2), (255, 255, 0), 2)
            cv2.putText(display, "BURAYA YON!", (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            if roi.size > 0:
                # HOG cikart
                feat = extract_hog(roi)
                
                if feat is not None:
                    try:
                        # Tahmin yap
                        pred_idx = clf.predict([feat])[0]
                        pred_label = le.inverse_transform([pred_idx])[0]
                        confidence = clf.predict_proba([feat])[0][pred_idx]
                        
                        # Gecmis guncelle
                        predictions_history.append((pred_label, confidence))
                        if len(predictions_history) > 15:
                            predictions_history.pop(0)
                        
                        # Ortalama tahmin
                        from collections import Counter
                        pred_counts = Counter([p[0] for p in predictions_history])
                        most_common = pred_counts.most_common(1)[0][0]
                        avg_conf = np.mean([p[1] for p in predictions_history if p[0] == most_common])
                        
                        # Renkli kutu
                        if avg_conf > 0.7:
                            color = (0, 255, 0)  # Yesil
                        elif avg_conf > 0.5:
                            color = (0, 255, 255)  # Sari
                        else:
                            color = (0, 165, 255)  # Turuncu
                        
                        cv2.rectangle(display, (x1, y1), (x2, y2), color, 4)
                        
                        # Ana tahmin
                        main_text = f"{most_common}: {avg_conf:.0%}"
                        cv2.putText(display, main_text, (x1, y1-40), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 3)
                        
                        # Tum tahminler (olasiliksiz)
                        y_offset = 50
                        cv2.putText(display, "SECENEKLER:", (20, y_offset), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                        
                        probs = clf.predict_proba([feat])[0]
                        sorted_indices = np.argsort(probs)[::-1]
                        
                        for i, idx in enumerate(sorted_indices[:len(le.classes_)]):
                            class_label = le.classes_[idx]
                            class_prob = probs[idx]
                            text = f"{i+1}. {class_label}: {class_prob:.0%}"
                            y_pos = y_offset + 30 * (i + 1)
                            if y_pos < h - 20:
                                c = (0, 255, 0) if i == 0 else (200, 200, 200)
                                cv2.putText(display, text, (20, y_pos), 
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, c, 2)
                    
                    except Exception as e:
                        cv2.putText(display, f"Hata: {str(e)[:40]}", (20, 100), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            cv2.putText(display, f"Frame: {frame_count}", (10, h-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            cv2.imshow('URUN SINIFLANDIRMA', display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\nKapandi.")


if __name__ == '__main__':
    main()
