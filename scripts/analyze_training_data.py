import os
import csv
import cv2
import numpy as np
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    
    # Eğitim verilerini görselleştir
    meta_file = os.path.join(split_root, 'train_metadata.csv')
    
    if not os.path.isfile(meta_file):
        print(f"Metadata dosyası bulunamadı: {meta_file}")
        return
    
    # Eğitim verilerini oku
    images_by_class = {}
    with open(meta_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pf = row.get('processed_file')
            label = row.get('label') or row.get('name') or 'unknown'
            
            if pf:
                img_path = os.path.join(processed, os.path.basename(pf))
                if os.path.isfile(img_path):
                    if label not in images_by_class:
                        images_by_class[label] = []
                    images_by_class[label].append(img_path)
    
    print("\n" + "="*60)
    print("EĞİTİM VERİSİ ANALİZİ")
    print("="*60)
    print(f"Toplam sınıf: {len(images_by_class)}")
    
    for label, images in sorted(images_by_class.items()):
        print(f"\n{label.upper()}: {len(images)} örnek")
        
        # Örnek görüntüleri göster
        if len(images) > 0:
            img = cv2.imread(images[0])
            if img is not None:
                h, w = img.shape[:2]
                print(f"  Boyut: {w}x{h}")
                print(f"  Örnek: {os.path.basename(images[0])}")
                
                # Örnek görüntüyü göster
                small = cv2.resize(img, (200, 200))
                cv2.imshow(f"Örnek: {label}", small)
    
    print("\n" + "="*60)
    print("Eğitim verilerini inceledim.")
    print("Herhangi bir tuşa basın...")
    print("="*60)
    
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
