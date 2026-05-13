r"""
SmartCart - Goruntu Tanima Test Scripti
=======================================
Kullanim:
  .\venv\Scripts\python.exe test_recognition.py
  .\venv\Scripts\python.exe test_recognition.py --key YOUR_GEMINI_API_KEY
  .\venv\Scripts\python.exe test_recognition.py --nowindow  (pencere olmadan test)

Kontroller (kamera modunda):
  SPACE  - Anlik fotograf cek ve urunu tani
  Q      - Cikis
"""
import sys, io
# Windows konsolunda UTF-8 zorla
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import cv2
import csv
import json
import re
import base64
import argparse
import random
import time
from io import BytesIO
from pathlib import Path

# Proje kök dizini
BASE_DIR = Path(__file__).parent
METADATA_CSV = BASE_DIR / "migros_dataset_merged" / "metadata.csv"

# ─────────────────────────────────────
# Ürün veritabanını yükle
# ─────────────────────────────────────
def load_products():
    products = []
    if not METADATA_CSV.exists():
        print(f"[HATA] metadata.csv bulunamadi: {METADATA_CSV}")
        return products
    with open(METADATA_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name  = row.get("name", "").strip()
            price = row.get("price", "").strip()
            file  = row.get("file", "").strip()
            if name and file:
                try:
                    price_f = float(price) if price else 0.0
                except ValueError:
                    price_f = 0.0
                # Mutlak yol kullan (Turkce karakter sorunu icin)
                img_path = BASE_DIR / "migros_dataset_merged" / file
                products.append({
                    "name":     name,
                    "price":    price_f,
                    "file":     file,
                    "img_path": img_path,   # Path nesnesi olarak tut
                })
    print(f"[OK] {len(products)} urun yuklendi.")
    return products

PRODUCTS = load_products()

# ─────────────────────────────────────
# Normalize (Turkce karakter toleransli)
# ─────────────────────────────────────
def normalize(text: str) -> str:
    tr_map = {
        "ı":"i","İ":"I","ş":"s","Ş":"S",
        "ğ":"g","Ğ":"G","ü":"u","Ü":"U",
        "ö":"o","Ö":"O","ç":"c","Ç":"C",
    }
    for k, v in tr_map.items():
        text = text.replace(k, v)
    return text.lower()

# ─────────────────────────────────────
# Gemini sonucunu ürünle eşleştir
# ─────────────────────────────────────
def find_best_match(raw_text: str):
    if not raw_text:
        return None, 0.0

    candidates = []

    # JSON blogu ara (markdown code fence icinde de olabilir)
    for pattern in [r'```json\s*(\{[^{}]+\})\s*```', r'(\{[^{}]+\})', r'(\[[^\[\]]+\])']:
        m = re.search(pattern, raw_text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
                if isinstance(obj, dict):
                    for k in ("name", "product", "urun", "result"):
                        if k in obj and obj[k]:
                            candidates.append(str(obj[k]))
                elif isinstance(obj, list):
                    candidates.extend(str(x) for x in obj if x)
            except Exception:
                pass
            break

    # Duz metin satirlari
    for line in raw_text.split("\n"):
        line = line.strip().strip("-•*`").strip()
        if 3 < len(line) < 120:
            candidates.append(line)

    if not candidates:
        return None, 0.0

    norm_cands = [normalize(c) for c in candidates]

    # Geri de kullanilmayacak jenerik kelimeler
    IGNORE = {"null", "none", "taninamadi", "bulunamadi", "urun", "goruntu",
              "cipsi", "atistirmalik", "bisküvi", "biskuvi", "cikolata"}

    best, best_score = None, 0.0

    for prod in PRODUCTS:
        p_norm   = normalize(prod["name"])
        p_tokens = set(p_norm.split()) - IGNORE
        if not p_tokens:
            continue

        for c in norm_cands:
            c_tokens = set(c.split()) - IGNORE
            if not c_tokens:
                continue

            common = p_tokens & c_tokens
            if not common:
                continue

            # Token overlap skoru
            score = len(common) / max(len(p_tokens), len(c_tokens))

            # Alt-string bonus: urun adinin bir parcasi input'ta geciyorsa
            if p_norm in c or c in p_norm:
                score += 0.5

            # Marka tespiti: ilk kelime eslesmesi (Doritos, Eti, Ülker...)
            p_brand = p_norm.split()[0] if p_norm.split() else ""
            c_brand = c.split()[0] if c.split() else ""
            if p_brand and p_brand == c_brand and p_brand not in IGNORE:
                score += 0.2   # Marka bonus

            if score > best_score:
                best_score = score
                best = prod

    # Minimum esik: 0.15 (marka tespiti icin yeterli)
    if best_score < 0.15:
        return None, best_score
    return best, best_score

# ─────────────────────────────────────
# Gemini API ile tanıma
# ─────────────────────────────────────
def recognize_with_gemini(frame_bgr, api_key: str):
    """Frame (BGR numpy array) → eşleşen ürün dict veya None"""
    from google import genai
    from google.genai import types as gt

    # Frame'i JPEG'e çevir
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None, 0.0, "JPEG encode hatasi"

    img_bytes = buf.tobytes()

    product_names = "\n".join(f"- {p['name']}" for p in PRODUCTS)

    prompt = (
        "Sen bir Migros market urunu tanimlama yapay zekasisin.\n"
        "Goruntude bir paketli urun var. Ambalaj net gorunmuyor olabilir.\n"
        "Marka, renk, sekil ve ambalaj tasarimina bakarak asagidaki listeden en yakin urunu bul.\n\n"
        "URUN LISTESI:\n"
        + product_names
        + "\n\nKURALLAR:\n"
        "- Kesinlikle listeden birini sec.\n"
        "- Emin olmadugin zaman bile en benzer urunu sec.\n"
        "- Asla 'taninamadi' veya null donderme, en iyi tahminini yap.\n"
        "- Sadece JSON formatinda dondur: {\"name\": \"<listeden tam urun adi>\"}\n"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=[
                gt.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                gt.Part.from_text(text=prompt),
            ],
        )
        raw = response.text.strip()
        print(f"\n Ham yanit: {raw}")
        product, score = find_best_match(raw)
        return product, score, raw
    except Exception as e:
        return None, 0.0, str(e)

# ─────────────────────────────────────
# Demo modu: rastgele ürün seç
# ─────────────────────────────────────
def recognize_demo(frame_bgr):
    time.sleep(0.5)  # Gerçekmiş gibi bekle
    product = random.choice(PRODUCTS) if PRODUCTS else None
    return product, 0.85, "DEMO_MOD"

# ─────────────────────────────────────
# Sonucu ekrana çiz
# ─────────────────────────────────────
def draw_result(frame, product, score, mode=""):
    h, w = frame.shape[:2]
    overlay = frame.copy()

    if product:
        # Yeşil panel
        cv2.rectangle(overlay, (0, h - 140), (w, h), (0, 80, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        name = product["name"]
        price = product["price"]
        conf_pct = int(score * 100)

        # Ürün adını sığdır (uzunsa kes)
        if len(name) > 45:
            name = name[:42] + "..."

        cv2.putText(frame, "URUN TANINDI!", (12, h - 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 255, 100), 2)
        cv2.putText(frame, name, (12, h - 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Fiyat: {price:.2f} TL   Guven: %{conf_pct}   [{mode}]",
                    (12, h - 42), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        # Urun resmini sag alt koseye ekle (Path nesnesi veya str destekli)
        img_p = product.get("img_path")
        if img_p:
            img_p = Path(img_p)
            if img_p.exists():
                try:
                    import numpy as np
                    data = np.frombuffer(img_p.read_bytes(), dtype=np.uint8)
                    prod_img = cv2.imdecode(data, cv2.IMREAD_COLOR)
                    if prod_img is not None:
                        prod_img = cv2.resize(prod_img, (100, 100))
                        frame[h - 120:h - 20, w - 110:w - 10] = prod_img
                        cv2.rectangle(frame, (w - 112, h - 122), (w - 8, h - 18),
                                      (100, 255, 100), 2)
                except Exception:
                    pass
    else:
        # Kırmızı panel - bulunamadı
        cv2.rectangle(overlay, (0, h - 80), (w, h), (0, 0, 120), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.putText(frame, "Urun bulunamadi - daha yakin tutun",
                    (12, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 100, 255), 2)

    return frame

# ─────────────────────────────────────
# Tek görüntü dosyası testi
# ─────────────────────────────────────
def test_image_file(img_path: str, api_key: str):
    # Turkce karakter iceren yollar icin numpy/PIL kullan
    p = Path(img_path)
    if not p.is_absolute():
        p = BASE_DIR / img_path
    if not p.exists():
        # Glob ile benzer isim ara
        hits = list((BASE_DIR / "migros_dataset_merged").glob("*.jpg"))
        if hits:
            p = hits[0]
            print(f"[INFO] Dosya bulunamadi, ilk gorsel kullaniliyor: {p.name}")
        else:
            print(f"[HATA] Goruntu bulunamadi: {img_path}")
            return
    # Path nesnesini bytes'a cevirerek OpenCV'ye ver
    import numpy as np
    data = np.frombuffer(p.read_bytes(), dtype=np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        print(f"[HATA] Goruntu decode edilemedi: {p}")
        return

    print(f"\nGoruntu test ediliyor: {img_path}")
    print("-" * 50)

    if api_key:
        product, score, raw = recognize_with_gemini(frame, api_key)
        mode = "AI"
    else:
        product, score, raw = recognize_demo(frame)
        mode = "DEMO"

    if product:
        print(f"[SONUC] Urun    : {product['name']}")
        print(f"        Fiyat   : {product['price']:.2f} TL")
        print(f"        Dosya   : {product['file']}")
        print(f"        Guven   : %{int(score*100)}")
        print(f"        Mod     : {mode}")
    else:
        print("[SONUC] Urun taninamadi.")

    result = draw_result(frame.copy(), product, score, mode)
    cv2.imshow("SmartCart - Goruntu Testi", result)
    print("\nDevam etmek icin herhangi bir tusa basin...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# ─────────────────────────────────────
# Canlı kamera testi
# ─────────────────────────────────────
def test_live_camera(api_key: str, camera_id: int = 0):
    print("\nKamera aciliyor...")
    print("KONTROLLER:")
    print("  SPACE  -> Fotograf cek ve urunu tani")
    print("  Q      -> Cikis")
    print("-" * 50)

    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[HATA] Kamera {camera_id} acilamadi!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    mode_label = "AI" if api_key else "DEMO"
    last_product = None
    last_score   = 0.0
    scanning     = False
    status_msg   = "SPACE: Urun tara  |  Q: Cikis"

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[HATA] Frame alinamadi!")
            break

        display = frame.copy()
        h, w = display.shape[:2]

        # Viewfinder çerçeve
        cx, cy = w // 2, h // 2
        size   = 220
        color  = (0, 220, 255) if not scanning else (0, 100, 255)
        thick  = 3
        # Köşe çizgileri
        for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            px, py = cx + dx * size // 2, cy + dy * size // 2
            cv2.line(display, (px, py), (px + dx*(-40), py), color, thick)
            cv2.line(display, (px, py), (px, py + dy*(-40)), color, thick)

        # Üst bilgi bandı
        cv2.rectangle(display, (0, 0), (w, 55), (20, 20, 20), -1)
        cv2.putText(display, f"SmartCart - Goruntu Tanima  [{mode_label}]",
                    (12, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 180, 0), 2)

        # Alt durum çubuğu
        if scanning:
            status_msg = "Taranıyor, lutfen bekleyin..."
            cv2.rectangle(display, (0, h-55), (w, h), (0, 60, 150), -1)
        elif last_product:
            display = draw_result(display, last_product, last_score, mode_label)
        else:
            cv2.rectangle(display, (0, h-55), (w, h), (30, 30, 30), -1)
            cv2.putText(display, status_msg, (12, h-18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        if scanning:
            cv2.putText(display, status_msg, (12, h-18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        cv2.imshow("SmartCart - Canli Kamera Testi", display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == 27:
            break

        elif key == ord(' ') and not scanning:
            scanning = True
            last_product = None
            cv2.imshow("SmartCart - Canli Kamera Testi", display)
            cv2.waitKey(1)

            print("\nFotograf aliniyor ve analiz ediliyor...")
            snap = frame.copy()

            if api_key:
                product, score, raw = recognize_with_gemini(snap, api_key)
            else:
                product, score, raw = recognize_demo(snap)

            last_product = product
            last_score   = score

            if product:
                print(f"[SONUC] {product['name']}  |  {product['price']:.2f} TL  |  %{int(score*100)} guven")
            else:
                print("[SONUC] Urun taninamadi.")

            scanning = False
            status_msg = "SPACE: Tekrar tara  |  Q: Cikis"

    cap.release()
    cv2.destroyAllWindows()
    print("\nKamera kapatildi.")

# ─────────────────────────────────────
# Ana Giriş
# ─────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SmartCart Goruntu Tanima Testi")
    parser.add_argument("--key",      default="", help="Gemini API key")
    parser.add_argument("--image",    default="", help="Test edilecek goruntu dosyasi (kamera yerine)")
    parser.add_argument("--camera",   type=int, default=0, help="Kamera ID (varsayilan: 0)")
    parser.add_argument("--nowindow", action="store_true", help="Pencere olmadan konsol ciktisi")
    args = parser.parse_args()

    # .env'den API key al
    env_file = BASE_DIR / ".env"
    api_key  = args.key
    if not api_key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")

    print("=" * 55)
    print("  SmartCart - Goruntu Tanima Test")
    print("=" * 55)
    print(f"  Urun sayisi : {len(PRODUCTS)}")
    print(f"  API key     : {'VAR (' + api_key[:8] + '...)' if api_key else 'YOK - Demo mod'}")
    print(f"  Mod         : {'AI Vision' if api_key else 'Demo (rastgele)'}")
    print("=" * 55)

    # --nowindow: pencere olmadan konsol testi (3 gorsel)
    if args.nowindow:
        import numpy as np
        imgs = sorted((BASE_DIR / "migros_dataset_merged").glob("*.jpg"))[:3]
        if not imgs:
            print("[HATA] Gorsel bulunamadi!")
            return
        for img_p in imgs:
            data  = np.frombuffer(img_p.read_bytes(), dtype=np.uint8)
            frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            print(f"\n--- Test: {img_p.name} ---")
            if api_key:
                product, score, raw = recognize_with_gemini(frame, api_key)
                mode = "AI"
            else:
                product, score, raw = recognize_demo(frame)
                mode = "DEMO"
            if product:
                print(f"  Sonuc : {product['name']}")
                print(f"  Fiyat : {product['price']:.2f} TL")
                print(f"  Guven : %{int(score*100)}")
                print(f"  Mod   : {mode}")
            else:
                print("  Sonuc : Taninamadi")
        return

    if args.image:
        test_image_file(args.image, api_key)
    else:
        test_live_camera(api_key, args.camera)


if __name__ == "__main__":
    main()
