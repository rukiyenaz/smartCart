import os
import csv
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing metadata.csv',
    )
    return parser.parse_args()

LABEL_RULES = [
    ('chips', ['doritos', 'cips', 'kraker', 'taco', 'corn', 'dippas', 'crax']),
    ('chocolate', ['browni', 'tadelle', 'karam', 'çikolata', 'cikolata', 'chocolate']),
    ('biscuit', ['bisküvi', 'biskuvi', 'mozaik', 'tutku', 'burçak', 'burcak', 'gofret', 'stix', 'biscolata']),
    ('nuts_seeds', ['ceviz', 'fındık', 'findik', 'ayçekirdeği', 'aycekirdegi', 'ayçekirdek', 'çekirdek', 'cekirdek']),
    ('gum_mint', ['first sensations', 'nane']),
]

def infer_label(name):
    text = (name or '').lower()
    for label, keywords in LABEL_RULES:
        if any(keyword in text for keyword in keywords):
            return label
    return 'other'

def process_file(src, dst):
    with open(src, newline='', encoding='utf-8') as inf:
        rows = list(csv.DictReader(inf))

    fieldnames = list(rows[0].keys()) if rows else []
    if 'label' not in fieldnames:
        fieldnames.append('label')

    out_rows = []
    for row in rows:
        row = dict(row)
        row['label'] = infer_label(row.get('name') or row.get('safe_name') or '')
        out_rows.append(row)

    with open(dst, 'w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    return out_rows

def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')

    src_root = os.path.join(root, 'metadata.csv')
    src_processed = os.path.join(processed, 'processed_metadata.csv')
    out_root = os.path.join(root, 'labeled_metadata.csv')
    out_processed = os.path.join(processed, 'labeled_metadata.csv')

    if not os.path.isfile(src_root):
        print('metadata.csv bulunamadı:', src_root)
        return

    root_rows = process_file(src_root, out_root)
    print('Yazıldı:', out_root)

    if os.path.isfile(src_processed):
        process_file(src_processed, out_processed)
        print('Yazıldı:', out_processed)

    # quick summary
    counts = {}
    for r in root_rows:
        counts[r['label']] = counts.get(r['label'], 0) + 1
    print('Label dağılımı:', counts)

if __name__ == '__main__':
    main()
