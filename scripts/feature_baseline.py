import os
import csv
import argparse
import numpy as np
from skimage import color, transform
from skimage.feature import hog
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
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


def load_split(split_name, processed, split_root):
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


def extract_hog(img_path):
    from skimage.io import imread

    im = imread(img_path)
    if im.ndim == 3:
        im = color.rgb2gray(im)
    im = transform.resize(im, IMG_SIZE, anti_aliasing=True)
    feat = hog(im, pixels_per_cell=(16, 16), cells_per_block=(2, 2), feature_vector=True)
    return feat


def build_dataset(split_name, processed, split_root):
    items = load_split(split_name, processed, split_root)
    X = []
    y = []
    for p, label in items:
        try:
            f = extract_hog(p)
            X.append(f)
            y.append(label)
        except Exception as e:
            print('skip', p, e)
    if not X:
        return None, None
    return np.vstack(X), np.array(y)


def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')

    X_train, y_train = build_dataset('train', processed, split_root)
    X_val, y_val = build_dataset('val', processed, split_root)
    X_test, y_test = build_dataset('test', processed, split_root)

    if X_train is None:
        print('No training data found.')
        return

    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)

    clf = LogisticRegression(max_iter=2000)
    clf.fit(X_train, y_train_enc)

    joblib.dump({'model': clf, 'label_encoder': le}, os.path.join(split_root, 'hog_logreg.joblib'))

    def evaluate(X, y, name):
        if X is None:
            print(name, 'no data')
            return

        mask = [lbl in le.classes_ for lbl in y]
        if not any(mask):
            print(name, 'no overlapping labels with train; skipping')
            return
        if not all(mask):
            skipped = sum(1 for m in mask if not m)
            print(f'{name}: skipping {skipped} samples with unseen labels')

        mask_arr = np.array(mask)
        X_f = X[mask_arr]
        y_f = np.array(y)[mask_arr]

        y_enc = le.transform(y_f)
        pred = clf.predict(X_f)
        acc = accuracy_score(y_enc, pred)
        print(f'{name} accuracy: {acc:.4f}')

        present = np.unique(y_enc)
        print(
            classification_report(
                y_enc,
                pred,
                labels=present,
                target_names=le.classes_[present],
                zero_division=0,
            )
        )

    evaluate(X_train, y_train, 'train')
    evaluate(X_val, y_val, 'val')
    evaluate(X_test, y_test, 'test')


if __name__ == '__main__':
    main()
