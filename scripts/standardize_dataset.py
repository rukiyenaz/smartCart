import os
import csv
import re
import argparse
from urllib.parse import urlparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing metadata.csv',
    )
    return parser.parse_args()

ILLEGAL = re.compile(r'[\\/*?:"<>|]')

def safe_filename(name):
    name = ILLEGAL.sub('_', name)
    name = name.strip().replace('\n',' ').replace('\r',' ')
    name = re.sub(r'\s+', ' ', name)
    return name

def ensure_ext(name, ext):
    if not os.path.splitext(name)[1]:
        return name + ext
    return name

def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    candidate = name
    i = 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return candidate

def main():
    args = parse_args()
    root = args.dataset_dir
    os.makedirs(root, exist_ok=True)
    metadata_path = os.path.join(root, 'metadata.csv')
    if not os.path.isfile(metadata_path):
        print('metadata.csv bulunamadı:', metadata_path)
        return

    backup_path = os.path.join(root, 'metadata_backup.csv')
    if not os.path.isfile(backup_path):
        os.rename(metadata_path, backup_path)
        print('Orijinal metadata yedeklendi ->', backup_path)
    else:
        # already backed up, read from original backup
        os.remove(metadata_path)

    with open(backup_path, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # Ensure 'file' field exists
    if 'file' not in fieldnames:
        fieldnames.append('file')

    seen_files = set(os.listdir(root))
    updated_rows = []

    for idx, row in enumerate(rows):
        # determine candidate filename
        original = None
        if row.get('file'):
            original = os.path.basename(row['file'])
        elif row.get('image'):
            try:
                parsed = urlparse(row['image'])
                original = os.path.basename(parsed.path)
            except Exception:
                original = None

        if not original or original == '':
            # fallback to safe_name or name
            key = row.get('safe_name') or row.get('name') or f'img_{idx+1}'
            original = safe_filename(key) + '.jpg'

        original = safe_filename(original)

        # make extension reasonable
        ext = os.path.splitext(original)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'):
            # try to infer from image url
            imgurl = row.get('image','')
            if imgurl and '.' in imgurl:
                ext = os.path.splitext(urlparse(imgurl).path)[1].lower() or '.jpg'
            else:
                ext = '.jpg'
            original = os.path.splitext(original)[0] + ext

        target = original
        # if a file with that name already exists but it's not the same row, create unique
        if target in seen_files:
            # if the file exists in disk and this row already points to it, keep
            # otherwise create a unique name
            current_file = row.get('file')
            if not current_file or os.path.basename(current_file) != target:
                target = unique_path(root, original)

        # if disk contains a differently-named file referenced by this row, rename it
        # search for possible source files: original name or image basename
        src_candidates = []
        if row.get('file'):
            src_candidates.append(os.path.join(root, os.path.basename(row['file'])))
        if row.get('image'):
            try:
                src_candidates.append(os.path.join(root, os.path.basename(urlparse(row['image']).path)))
            except Exception:
                pass

        renamed = False
        for src in src_candidates:
            if os.path.isfile(src):
                tgt_path = os.path.join(root, target)
                if os.path.abspath(src) != os.path.abspath(tgt_path):
                    try:
                        os.rename(src, tgt_path)
                        print(f'Renamed: {os.path.basename(src)} -> {target}')
                    except Exception as e:
                        print('Rename hata:', e)
                renamed = True
                seen_files.add(target)
                break

        # if not found on disk but a file with same name exists, assume it's correct
        if not renamed and target in seen_files:
            pass

        # if nothing exists on disk but an alternative file (exact original) exists, rename it
        # otherwise nothing to do except record the target name

        row['file'] = target
        updated_rows.append(row)

    # write updated metadata
    out_path = os.path.join(root, 'metadata.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        for r in updated_rows:
            writer.writerow(r)

    print('Standart metadata yazıldı ->', out_path)

if __name__ == '__main__':
    main()
