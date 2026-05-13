import os
import csv
import argparse
import numpy as np
from skimage import color, transform
from skimage.feature import hog
from skimage.io import imread
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import joblib

IMG_SIZE = (128, 128)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory',
    )
    return parser.parse_args()


def extract_features(img_path):
    """HOG + Renk histogram özellikleri"""
    try:
        im = imread(img_path)
        
        # HOG (gri tonlama)
        if im.ndim == 3:
            gray = color.rgb2gray(im)
        else:
            gray = im
        
        gray = transform.resize(gray, IMG_SIZE, anti_aliasing=True)
        hog_feat = hog(gray, pixels_per_cell=(16, 16), cells_per_block=(2, 2), 
                      feature_vector=True, channel_axis=None)
        
        # Renk histogram
        if im.ndim == 3:
            im_resized = transform.resize(im, IMG_SIZE, anti_aliasing=True)
            # RGB kanallarından histogram
            hist_r = np.histogram(im_resized[:,:,0], bins=16)[0] / im_resized.size
            hist_g = np.histogram(im_resized[:,:,1], bins=16)[0] / im_resized.size
            hist_b = np.histogram(im_resized[:,:,2], bins=16)[0] / im_resized.size
            color_feat = np.concatenate([hist_r, hist_g, hist_b])
        else:
            color_feat = np.zeros(48)
        
        # Birleştir
        features = np.concatenate([hog_feat, color_feat])
        return features
    except Exception as e:
        return None


def load_split(split_name, processed, split_root):
    """Veri seti yükle"""
    meta = os.path.join(split_root, f'{split_name}_metadata.csv')
    items = []
    
    if not os.path.isfile(meta):
        return items
    
    with open(meta, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        for r in reader:
            pf = r.get('processed_file')
            if not pf:
                continue
            img_path = os.path.join(processed, os.path.basename(pf))
            if os.path.isfile(img_path):
                label = r.get('label') or r.get('name') or r.get('safe_name') or 'unknown'
                items.append((img_path, label))
    
    return items


def build_dataset(split_name, processed, split_root):
    """Dataset oluştur"""
    items = load_split(split_name, processed, split_root)
    X = []
    y = []
    
    for p, label in items:
        feat = extract_features(p)
        if feat is not None:
            X.append(feat)
            y.append(label)
        else:
            print(f"Skip: {p}")
    
    if not X:
        return None, None
    
    return np.vstack(X), np.array(y)


def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    
    print("Veri seti yükleniyor...")
    X_train, y_train = build_dataset('train', processed, split_root)
    X_val, y_val = build_dataset('val', processed, split_root)
    X_test, y_test = build_dataset('test', processed, split_root)
    
    if X_train is None:
        print("Eğitim verisi yok!")
        return
    
    print(f"Eğitim: {X_train.shape}, Val: {X_val.shape if X_val is not None else 'Yok'}, Test: {X_test.shape if X_test is not None else 'Yok'}")
    print(f"Özellik boyutu: {X_train.shape[1]}")
    
    # Label encoder
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    
    print(f"\nSınıflar: {list(le.classes_)}")
    
    # Random Forest modeli
    print("\nRandom Forest modeli eğitiliyor...")
    clf = RandomForestClassifier(n_estimators=200, max_depth=20, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train_enc)
    
    # Kaydet
    model_path = os.path.join(split_root, 'hog_rf_model.joblib')
    joblib.dump({'model': clf, 'label_encoder': le}, model_path)
    print(f"Model kaydedildi: {model_path}")
    
    # Değerlendirme
    def evaluate(X, y, name):
        if X is None:
            print(f"{name}: Veri yok")
            return
        
        mask = np.array([lbl in le.classes_ for lbl in y])
        if not np.any(mask):
            print(f"{name}: Uyuşan etiket yok")
            return
        
        y_filtered = y[mask]
        X_filtered = X[mask]
        
        y_pred_enc = clf.predict(X_filtered)
        y_pred = le.inverse_transform(y_pred_enc)
        
        acc = accuracy_score(y_filtered, y_pred)
        print(f"\n{name} Accuracy: {acc:.4f}")
        print(classification_report(y_filtered, y_pred, zero_division=0))
    
    evaluate(X_train, y_train, "TRAIN")
    evaluate(X_val, y_val, "VALIDATION")
    evaluate(X_test, y_test, "TEST")
    
    print("\n✓ Eğitim tamamlandı!")


if __name__ == '__main__':
    main()
