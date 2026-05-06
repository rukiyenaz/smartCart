import os
import csv
import shutil
from pathlib import Path


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def unique_name(dst_dir, filename):
    base, ext = os.path.splitext(filename)
    candidate = filename
    idx = 1
    while os.path.exists(os.path.join(dst_dir, candidate)):
        candidate = f"{base}_{idx}{ext}"
        idx += 1
    return candidate


def resolve_source_file(dataset_dir, row_file_value):
    if not row_file_value:
        return None
    # metadata may contain absolute, relative, or prefixed paths
    base = os.path.basename(row_file_value)
    candidates = [
        os.path.join(dataset_dir, row_file_value),
        os.path.join(dataset_dir, base),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def merge_dataset(src_dir, merged_dir, prefix, out_rows):
    meta_path = os.path.join(src_dir, 'metadata.csv')
    if not os.path.isfile(meta_path):
        print('metadata.csv bulunamadı:', meta_path)
        return 0

    copied = 0
    with open(meta_path, newline='', encoding='utf-8') as inf:
        rows = list(csv.DictReader(inf))

    for row in rows:
        src_file = resolve_source_file(src_dir, row.get('file', ''))
        if src_file is None:
            continue

        prefixed = f"{prefix}_{os.path.basename(src_file)}"
        dst_name = unique_name(merged_dir, prefixed)
        dst_file = os.path.join(merged_dir, dst_name)
        shutil.copy2(src_file, dst_file)

        new_row = dict(row)
        new_row['file'] = dst_name
        out_rows.append(new_row)
        copied += 1

    return copied


def main():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    dataset_a = os.path.join(base_dir, 'migros_dataset')
    dataset_b = os.path.join(base_dir, 'migros_dataset_cikolata')
    merged = os.path.join(base_dir, 'migros_dataset_merged')
    ensure_dir(merged)

    out_rows = []
    a_count = merge_dataset(dataset_a, merged, 'snack', out_rows)
    b_count = merge_dataset(dataset_b, merged, 'choco', out_rows)

    if not out_rows:
        print('Birleştirilecek kayıt bulunamadı.')
        return

    fieldnames = list(out_rows[0].keys())
    out_meta = os.path.join(merged, 'metadata.csv')
    with open(out_meta, 'w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print('Birleştirme tamamlandı:', merged)
    print('Snack kayıt:', a_count)
    print('Çikolata kayıt:', b_count)
    print('Toplam kayıt:', len(out_rows))


if __name__ == '__main__':
    main()
