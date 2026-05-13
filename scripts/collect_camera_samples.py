import os
import cv2
import numpy as np
import argparse
from datetime import datetime

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
    
    print("="*60)
    print("KAMERADAN URUN ORNEGI KAYDET")
    print("="*60)
    print("\nKullani: Ürünü göster, 'SPACE' tuşuna bas (kaydet)")
    print("Sınıf seç:")
    print("  1 = biscuit")
    print("  2 = chips")
    print("  3 = chocolate")
    print("  4 = gum_mint")
    print("  5 = nuts_seeds")
    print("  6 = other")
    print("  q = Çıkış\n")
    
    classes = {
        '1': 'biscuit',
        '2': 'chips',
        '3': 'chocolate',
        '4': 'gum_mint',
        '5': 'nuts_seeds',
        '6': 'other'
    }
    
    cap = cv2.VideoCapture(args.camera_id)
    if not cap.isOpened():
        print("Kamera açılamadı!")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    frame_count = 0
    sample_count = {cls: 0 for cls in classes.values()}
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            display = frame.copy()
            h, w = frame.shape[:2]
            
            # Merkez ROI göster
            center_x, center_y = w // 2, h // 2
            roi_size = 280
            
            x1 = max(0, center_x - roi_size // 2)
            y1 = max(0, center_y - roi_size // 2)
            x2 = min(w, center_x + roi_size // 2)
            y2 = min(h, center_y + roi_size // 2)
            
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 255), 3)
            cv2.putText(display, "SPACE: Kaydet | Sinif: 1-6 | Q: Cikis", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display, f"Frame: {frame_count}", (10, h-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            # Toplam sayıları göster
            y_pos = 70
            for cls, count in sample_count.items():
                text = f"{cls}: {count} örnek"
                cv2.putText(display, text, (10, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                y_pos += 30
            
            cv2.imshow('Veri Toplama', display)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            
            elif key == ord(' '):  # SPACE
                # Sınıf sor
                while True:
                    print("\nSınıf seç (1-6): ", end='')
                    user_input = input().strip()
                    if user_input in classes:
                        cls = classes[user_input]
                        break
                    elif user_input == 'q':
                        break
                    else:
                        print("Geçersiz!")
                        continue
                
                if user_input == 'q':
                    break
                
                # Kaydet
                roi = frame[y1:y2, x1:x2]
                if roi.size > 0:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                    filename = f"camera_{cls}_{timestamp}.jpg"
                    filepath = os.path.join(processed, filename)
                    
                    cv2.imwrite(filepath, roi)
                    sample_count[cls] += 1
                    
                    print(f"✓ Kaydedildi: {filename}")
    
    except KeyboardInterrupt:
        pass
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        
        print("\n" + "="*60)
        print("OZET:")
        print("="*60)
        total = sum(sample_count.values())
        print(f"Toplam: {total} örnek")
        for cls, count in sample_count.items():
            if count > 0:
                print(f"  {cls}: {count}")
        print("\nSonraki adım: python scripts/update_metadata.py --dataset-dir migros_dataset_merged")


if __name__ == '__main__':
    main()
