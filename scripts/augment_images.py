import os
import csv
import random
import argparse
from PIL import Image, ImageEnhance

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migros_dataset'),
        help='Path to dataset directory containing processed split metadata',
    )
    return parser.parse_args()

N_AUG = 3
SEED = 42
random.seed(SEED)

def random_brightness(img, factor_min=0.8, factor_max=1.2):
    enhancer = ImageEnhance.Brightness(img)
    factor = random.uniform(factor_min, factor_max)
    return enhancer.enhance(factor)

def random_rotate(img, max_deg=15):
    deg = random.uniform(-max_deg, max_deg)
    return img.rotate(deg, resample=Image.BICUBIC, expand=False)

def random_flip(img):
    if random.random() < 0.5:
        return img.transpose(Image.FLIP_LEFT_RIGHT)
    return img

def random_crop_resize(img, min_scale=0.9):
    w, h = img.size
    scale = random.uniform(min_scale, 1.0)
    nw, nh = int(w * scale), int(h * scale)
    left = random.randint(0, w - nw) if w - nw > 0 else 0
    top = random.randint(0, h - nh) if h - nh > 0 else 0
    cropped = img.crop((left, top, left + nw, top + nh))
    return cropped.resize((w, h), Image.LANCZOS)

def augment_image(img):
    img = random_rotate(img)
    img = random_flip(img)
    img = random_crop_resize(img)
    img = random_brightness(img)
    return img

def main():
    args = parse_args()
    root = args.dataset_dir
    processed = os.path.join(root, 'processed')
    split_root = os.path.join(processed, 'dataset_split')
    aug_dir = os.path.join(split_root, 'train_aug')
    os.makedirs(aug_dir, exist_ok=True)

    meta = os.path.join(split_root, 'train_metadata.csv')
    if not os.path.isfile(meta):
        print('train_metadata.csv bulunamadı:', meta)
        return

    rows = []
    with open(meta, newline='', encoding='utf-8') as inf:
        reader = csv.DictReader(inf)
        for r in reader:
            rows.append(r)

    out_rows = []
    for r in rows:
        p = r.get('processed_file','')
        if not p:
            continue
        src = os.path.join(processed, os.path.basename(p))
        if not os.path.isfile(src):
            continue
        # copy original into aug folder as well
        base = os.path.splitext(os.path.basename(src))[0]
        with Image.open(src) as im:
            # save original copy
            orig_dst = os.path.join(aug_dir, base + '_orig.jpg')
            im.convert('RGB').save(orig_dst, format='JPEG', quality=90)
            r_copy = dict(r)
            r_copy['processed_file'] = os.path.relpath(orig_dst, processed)
            out_rows.append(r_copy)

            for i in range(1, N_AUG + 1):
                aug = augment_image(im.copy())
                out_name = f"{base}_aug{i}.jpg"
                out_path = os.path.join(aug_dir, out_name)
                aug.convert('RGB').save(out_path, format='JPEG', quality=90)
                r_aug = dict(r)
                r_aug['processed_file'] = os.path.relpath(out_path, processed)
                out_rows.append(r_aug)

    out_meta = os.path.join(split_root, 'train_aug_metadata.csv')
    fieldnames = list(out_rows[0].keys()) if out_rows else ['processed_file']
    with open(out_meta, 'w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        for rr in out_rows:
            writer.writerow(rr)

    print('Augmentasyon tamamlandı ->', aug_dir)

if __name__ == '__main__':
    main()
