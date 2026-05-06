import os
import csv
import argparse
from PIL import Image, UnidentifiedImageError

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing metadata.csv',
    )
    return parser.parse_args()

MAX_SIDE = 512
MIN_PIXELS = 32

def process_image(src_path, dst_path):
    with Image.open(src_path) as im:
        im = im.convert('RGB')
        w, h = im.size
        if w < MIN_PIXELS or h < MIN_PIXELS:
            return None, (w, h), 'too_small'
        scale = min(1.0, MAX_SIDE / max(w, h))
        if scale < 1.0:
            new_size = (int(w * scale), int(h * scale))
            im = im.resize(new_size, Image.LANCZOS)
        im.save(dst_path, format='JPEG', quality=90)
        return dst_path, im.size, None

def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    os.makedirs(processed, exist_ok=True)

    meta_in = os.path.join(root, 'metadata.csv')
    if not os.path.isfile(meta_in):
        print('metadata.csv bulunamadı:', meta_in)
        return

    rows = []
    with open(meta_in, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        for r in reader:
            rows.append(r)

    out_rows = []
    log_lines = []

    for i, row in enumerate(rows):
        fname = row.get('file') or ''
        src = os.path.join(root, fname)
        base, _ = os.path.splitext(os.path.basename(fname))
        processed_name = base + '.jpg'
        dst = os.path.join(processed, processed_name)

        if not os.path.isfile(src):
            log_lines.append(f'MISSING:\t{fname}')
            row_out = {**row, 'original_file': fname, 'processed_file': '', 'processed_size': ''}
            out_rows.append(row_out)
            continue

        try:
            result, size, reason = process_image(src, dst)
            if reason:
                log_lines.append(f'SKIPPED ({reason}):\t{fname} size={size}')
                row_out = {**row, 'original_file': fname, 'processed_file': '', 'processed_size': f'{size[0]}x{size[1]}' }
            else:
                log_lines.append(f'PROCESSED:\t{fname} -> {os.path.relpath(dst, root)} size={size}')
                row_out = {**row, 'original_file': fname, 'processed_file': os.path.relpath(dst, root), 'processed_size': f'{size[0]}x{size[1]}' }
        except UnidentifiedImageError:
            log_lines.append(f'UNIDENTIFIED:\t{fname}')
            row_out = {**row, 'original_file': fname, 'processed_file': '', 'processed_size': ''}
        except Exception as e:
            log_lines.append(f'ERROR:\t{fname}\t{e}')
            row_out = {**row, 'original_file': fname, 'processed_file': '', 'processed_size': ''}

        out_rows.append(row_out)

    out_meta = os.path.join(processed, 'processed_metadata.csv')
    fieldnames = list(out_rows[0].keys()) if out_rows else ['original_file','processed_file','processed_size']
    with open(out_meta, 'w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    with open(os.path.join(processed, 'processing_log.txt'), 'w', encoding='utf-8') as lf:
        lf.write('\n'.join(log_lines))

    print('İşlem tamamlandı. İşlenen metadata:', out_meta)

if __name__ == '__main__':
    main()
