import os
import csv
import numpy as np
import argparse
from skimage import color, transform
from skimage.feature import hog
from skimage.io import imread
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
import joblib

IMG_SIZE = (128, 128)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing processed split metadata',
    )
    return parser.parse_args()


def extract_hog(img_path):
    """HOG özelliklerini çıkart"""
    try:
        im = imread(img_path)
        if im.ndim == 3:
            im = color.rgb2gray(im)
        im = transform.resize(im, IMG_SIZE, anti_aliasing=True)
        feat = hog(im, pixels_per_cell=(16, 16), cells_per_block=(2, 2), feature_vector=True)
        return feat
    except Exception as e:
        print(f"Hata: {img_path} - {e}")
        return None


def load_test_data(processed, split_root):
    """Test verilerini yükle"""
    meta_file = os.path.join(split_root, 'test_metadata.csv')
    X = []
    y = []
    
    if not os.path.isfile(meta_file):
        print(f"Metadata dosyası bulunamadı: {meta_file}")
        return None, None
    
    with open(meta_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pf = row.get('processed_file')
            if not pf:
                continue
            
            img_path = os.path.join(processed, os.path.basename(pf))
            if not os.path.isfile(img_path):
                continue
            
            label = row.get('label') or row.get('name') or row.get('safe_name') or 'unknown'
            
            feat = extract_hog(img_path)
            if feat is not None:
                X.append(feat)
                y.append(label)
    
    if not X:
        return None, None
    
    return np.vstack(X), np.array(y)


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
    
    # Test verilerini yükle
    print("Test verileri yükleniyor...")
    X_test, y_test = load_test_data(processed, split_root)
    
    if X_test is None or len(X_test) == 0:
        print("Test verisi yüklenemedi")
        return
    
    print(f"Test verileri: {X_test.shape[0]} örnek, {X_test.shape[1]} özellik")
    
    # Tahminler yap
    print("\nTahminler yapılıyor...")
    y_test_pred_labels = clf.predict(X_test)
    y_test_pred_labels = le.inverse_transform(y_test_pred_labels)
    
    # Etiketleri eğitim setine göre filtrele
    mask = np.array([lbl in le.classes_ for lbl in y_test])
    y_test_filtered = y_test[mask]
    y_test_pred_filtered = y_test_pred_labels[mask]
    
    if len(y_test_filtered) == 0:
        print("Test etiketleri eğitim setindeki etiketlerle eşleşmiyor")
        return
    
    # Metrikleri hesapla
    print("\n" + "="*50)
    print("MODEL DEĞERLENDİRME SONUÇLARI")
    print("="*50)
    
    accuracy = accuracy_score(y_test_filtered, y_test_pred_filtered)
    print(f"\nDoğruluk (Accuracy): {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Sınıf bazlı metrikleri hesapla
    try:
        precision = precision_score(y_test_filtered, y_test_pred_filtered, average='weighted', zero_division=0)
        recall = recall_score(y_test_filtered, y_test_pred_filtered, average='weighted', zero_division=0)
        f1 = f1_score(y_test_filtered, y_test_pred_filtered, average='weighted', zero_division=0)
        
        print(f"Hassasiyet (Precision): {precision:.4f}")
        print(f"Duyarlılık (Recall): {recall:.4f}")
        print(f"F1-Skoru: {f1:.4f}")
    except Exception as e:
        print(f"Metrikleri hesaplanamadı: {e}")
    
    # Detaylı sınıf bazlı rapor
    print("\n" + "-"*50)
    print("SINIF BAZLI RAPOR")
    print("-"*50)
    print(classification_report(y_test_filtered, y_test_pred_filtered, zero_division=0))
    
    # Confusion Matrix
    print("\n" + "-"*50)
    print("KARIŞIKLIK MATRİSİ")
    print("-"*50)
    cm = confusion_matrix(y_test_filtered, y_test_pred_filtered, labels=le.classes_)
    print("Sınıflar:", le.classes_)
    print(cm)
    
    # Örnek tahminleri göster
    print("\n" + "-"*50)
    print("ÖRNEK TAHMİNLER (İlk 10)")
    print("-"*50)
    for i in range(min(10, len(y_test_filtered))):
        actual = y_test_filtered[i]
        predicted = y_test_pred_filtered[i]
        status = "✓" if actual == predicted else "✗"
        print(f"{status} Gerçek: {actual:20} | Tahmin: {predicted}")
    
    print("\n" + "="*50)
    print("Test tamamlandı!")
    print("="*50)


if __name__ == '__main__':
    main()
