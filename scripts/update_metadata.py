import os
import csv
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
    
    meta_file = os.path.join(split_root, 'train_metadata.csv')
    
    if not os.path.isfile(meta_file):
        print(f"Metadata dosyası bulunamadı: {meta_file}")
        return
    
    # Mevcut metadata'yı oku
    rows = []
    with open(meta_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    print(f"Mevcut eğitim verisi: {len(rows)} örnek")
    
    # processed klasöründe camera_ başlayan dosyaları ara
    processed_files = list(Path(processed).glob('camera_*.jpg'))
    
    if not processed_files:
        print("Kameradan yeni örnek bulunamadı!")
        return
    
    print(f"Kameradan yeni örnek: {len(processed_files)}")
    
    # Yeni satırlar ekle
    new_rows = []
    for fpath in processed_files:
        # Dosya adından sınıf ve timestamp çıkart
        # Format: camera_<class>_<timestamp>.jpg
        name = fpath.stem
        parts = name.split('_')
        
        if len(parts) >= 3:
            cls = parts[1]  # class name
        else:
            cls = 'other'
        
        row = {
            'processed_file': fpath.name,
            'label': cls,
            'name': fpath.name,
            'safe_name': cls
        }
        
        # Zaten var mı kontrol et
        exists = any(r.get('processed_file') == fpath.name for r in rows)
        if not exists:
            new_rows.append(row)
            print(f"  + {fpath.name} ({cls})")
    
    # Metadata'yı güncelle
    rows.extend(new_rows)
    
    with open(meta_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n✓ Metadata güncellendi!")
    print(f"  Eski: {len(rows) - len(new_rows)} örnek")
    print(f"  Yeni: {len(new_rows)} örnek")
    print(f"  Toplam: {len(rows)} örnek")
    
    print("\nSonraki adım: python scripts/train_resnet.py --dataset-dir migros_dataset_merged")


if __name__ == '__main__':
    main()
