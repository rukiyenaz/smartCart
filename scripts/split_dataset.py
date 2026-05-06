import os
import csv
import shutil
import random
import argparse
from collections import Counter

from sklearn.model_selection import train_test_split

RATIOS = (0.7, 0.15, 0.15)  # train, val, test


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing processed metadata',
    )
    return parser.parse_args()


def main(seed=42):
    random.seed(seed)
    args = parse_args()

    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    os.makedirs(split_root, exist_ok=True)

    meta_candidates = [
        os.path.join(processed, 'labeled_metadata.csv'),
        os.path.join(processed, 'processed_metadata.csv'),
    ]
    meta = next((p for p in meta_candidates if os.path.isfile(p)), None)
    if meta is None:
        print('metadata bulunamadı:', meta_candidates)
        return

    rows = []
    with open(meta, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        for r in reader:
            rows.append(r)

    items = []
    for r in rows:
        p = r.get('processed_file', '')
        if not p:
            continue
        fp = os.path.join(processed, os.path.basename(p))
        if os.path.isfile(fp):
            items.append((fp, r))

    if not items:
        print('No items to split.')
        return

    labels = [r.get('label', 'unknown') for _, r in items]
    counts = Counter(labels)
    stratify = labels if len(counts) > 1 and min(counts.values()) >= 2 else None

    train_items, temp_items = train_test_split(
        items,
        train_size=RATIOS[0],
        random_state=seed,
        shuffle=True,
        stratify=stratify,
    )

    temp_labels = [r.get('label', 'unknown') for _, r in temp_items]
    temp_counts = Counter(temp_labels)
    temp_stratify = temp_labels if stratify is not None and len(temp_counts) > 1 and min(temp_counts.values()) >= 2 else None

    val_ratio_of_temp = RATIOS[1] / (RATIOS[1] + RATIOS[2])
    val_items, test_items = train_test_split(
        temp_items,
        train_size=val_ratio_of_temp,
        random_state=seed,
        shuffle=True,
        stratify=temp_stratify,
    )

    splits = {'train': train_items, 'val': val_items, 'test': test_items}

    for split_name, split_items in splits.items():
        out_dir = os.path.join(split_root, split_name)
        os.makedirs(out_dir, exist_ok=True)

        csv_path = os.path.join(split_root, f'{split_name}_metadata.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as outf:
            fieldnames = list(rows[0].keys()) if rows else ['processed_file']
            writer = csv.DictWriter(outf, fieldnames=fieldnames)
            writer.writeheader()
            for fp, r in split_items:
                dst = os.path.join(out_dir, os.path.basename(fp))
                shutil.copy2(fp, dst)
                r_copy = dict(r)
                r_copy['processed_file'] = os.path.join(split_name, os.path.basename(fp))
                writer.writerow(r_copy)

    print('Split tamamlandı. Çıktı:', split_root)


if __name__ == '__main__':
    main()
