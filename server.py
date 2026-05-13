"""
SmartCart - Urun Tanima Backend Sunucusu
Google Gemini Vision API kullanarak urun tanima yapar.

Kurulum:
    pip install flask flask-cors google-genai pillow

Kullanım:
    python server.py
    
    .env dosyasına GEMINI_API_KEY=your_key ekleyin
    veya doğrudan GEMINI_API_KEY ortam değişkeni olarak set edin.
"""

import os
import csv
import base64
import json
import re
from io import BytesIO
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from PIL import Image
from google import genai
from google.genai import types as genai_types

# ──────────────────────────────────────────────
# Yapılandırma
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
METADATA_CSV = BASE_DIR / "migros_dataset_merged" / "metadata.csv"
IMAGES_DIR   = BASE_DIR / "migros_dataset_merged"

# .env desteği (isteğe bağlı)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app, origins="*")

# ──────────────────────────────────────────────
# Ürün Veritabanı Yükle
# ──────────────────────────────────────────────
def load_products():
    products = []
    if not METADATA_CSV.exists():
        print(f"⚠️  metadata.csv bulunamadı: {METADATA_CSV}")
        return products
    
    with open(METADATA_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name  = row.get("name", "").strip()
            price_str = row.get("price", "").strip()
            file  = row.get("file", "").strip()
            if name and file:
                try:
                    price = float(price_str) if price_str else 0.0
                except ValueError:
                    price = 0.0
                products.append({
                    "name":  name,
                    "price": price,
                    "file":  file,
                    "img":   f"migros_dataset_merged/{file}"
                })
    print(f"[OK] {len(products)} urun yuklendi.")
    return products

PRODUCTS = load_products()

# AI istemcisi başlat
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    print("[OK] AI Vision istemcisi hazir.")
else:
    print("[WARN] GEMINI_API_KEY bulunamadi. Demo/simulasyon modu aktif.")

# ──────────────────────────────────────────────
# Ürün Eşleştirme
# ──────────────────────────────────────────────
def normalize(text: str) -> str:
    """Türkçe karakterler dahil normalize et"""
    replacements = {
        "ı": "i", "İ": "I", "ş": "s", "Ş": "S",
        "ğ": "g", "Ğ": "G", "ü": "u", "Ü": "U",
        "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.lower()


def find_best_match(gemini_result: str) -> dict | None:
    """
    Gemini'nin döndürdüğü JSON/metin içindeki ürün adını
    PRODUCTS listesiyle eşleştir.
    """
    if not gemini_result:
        return None

    # Gemini JSON bloğunu parse etmeye çalış
    candidate_names = []
    
    # JSON bloğu ara
    json_match = re.search(r'\{[^{}]+\}', gemini_result, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            # 'matches', 'products', 'items', 'name' gibi alanları tara
            for key in ("matches", "products", "items"):
                if key in data and isinstance(data[key], list):
                    candidate_names.extend(data[key])
            if "name" in data:
                candidate_names.append(data["name"])
            if "product" in data:
                candidate_names.append(data["product"])
        except json.JSONDecodeError:
            pass
    
    # JSON array dene
    arr_match = re.search(r'\[([^\[\]]+)\]', gemini_result)
    if arr_match:
        try:
            arr = json.loads(arr_match.group())
            if isinstance(arr, list):
                candidate_names.extend([str(x) for x in arr])
        except:
            pass

    # Düz metin satırlarını da ekle
    for line in gemini_result.split("\n"):
        line = line.strip().strip("-•*").strip()
        if 3 < len(line) < 120:
            candidate_names.append(line)

    # Her adayı PRODUCTS ile eşleştir (token overlap skoru)
    best_product = None
    best_score   = 0

    norm_candidates = [normalize(c) for c in candidate_names]

    for product in PRODUCTS:
        p_norm   = normalize(product["name"])
        p_tokens = set(p_norm.split())
        
        for c_norm in norm_candidates:
            c_tokens = set(c_norm.split())
            if not c_tokens:
                continue
            
            # Jaccard benzeri overlap
            common = p_tokens & c_tokens
            if not common:
                continue
            
            score = len(common) / max(len(p_tokens), len(c_tokens))
            
            # Exact match bonus
            if p_norm in c_norm or c_norm in p_norm:
                score += 0.5
            
            if score > best_score:
                best_score   = score
                best_product = product

    # Çok düşük skor → sonuç yok
    if best_score < 0.3:
        return None
    
    return best_product


# ──────────────────────────────────────────────
# Frontend Servisi
# ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_file(BASE_DIR / "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    # API rotalarına dokunma
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    try:
        return send_from_directory(str(BASE_DIR), filename)
    except Exception:
        return send_file(BASE_DIR / "index.html")

# ──────────────────────────────────────────────
# API: Ürün Listesi
# ──────────────────────────────────────────────
@app.route("/api/products", methods=["GET"])
def get_products():
    return jsonify(PRODUCTS)


# ──────────────────────────────────────────────
# API: Görüntü Tanıma
# ──────────────────────────────────────────────
@app.route("/api/recognize", methods=["POST"])
def recognize():
    data = request.get_json(silent=True) or {}
    
    image_b64 = data.get("image", "")
    if not image_b64:
        return jsonify({"error": "Görüntü verisi eksik"}), 400
    
    # Base64 header kaldır
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    # Gemini API mevcut değilse simülasyon yap
    if not gemini_client:
        import random
        product = random.choice(PRODUCTS) if PRODUCTS else None
        if not product:
            return jsonify({"found": False, "message": "Urun bulunamadi"})
        return jsonify({
            "found":      True,
            "product":    product,
            "confidence": 0.85,
            "mode":       "demo"
        })

    # Görüntüyü PIL ile yükle
    try:
        img_bytes = base64.b64decode(image_b64)
        img = Image.open(BytesIO(img_bytes))
        # Boyutu küçült (hız için)
        img.thumbnail((800, 800), Image.LANCZOS)
    except Exception as e:
        return jsonify({"error": f"Görüntü işlenemedi: {e}"}), 400

    # Ürün listesini prompt'a ekle
    product_names = "\n".join(f"- {p['name']}" for p in PRODUCTS)

    prompt = f"""Sen bir supermarket urunu tanima AI'sisin.
Asagidaki goruntude hangi urun gorunuyor?

Sadece bu listedeki urunlerden eslestirme yap:
{product_names}

Eger listede eslesen bir urun varsa, tam urun adini JSON formatinda dondur:
{{"name": "<tam urun adi>"}}

Eger hicbir urun taninamazsa:
{{"name": null}}

Sadece JSON dondur, baska aciklama ekleme."""

    try:
        # PIL Image'ı byte'a çevir
        img_buf = BytesIO()
        img.save(img_buf, format="JPEG", quality=85)
        img_bytes_out = img_buf.getvalue()
        
        response = gemini_client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=[
                genai_types.Part.from_bytes(data=img_bytes_out, mime_type="image/jpeg"),
                genai_types.Part.from_text(text=prompt),
            ],
        )
        gemini_text = response.text.strip()
        print(f"AI yaniti: {gemini_text}")
    except Exception as e:
        print(f"AI hatasi: {e}")
        return jsonify({"error": f"AI servisi hatasi: {str(e)}"}), 500

    # Eşleştir
    matched = find_best_match(gemini_text)

    if matched:
        return jsonify({
            "found":       True,
            "product":     matched,
            "confidence":  0.90,
            "ai_raw":      gemini_text,
            "mode":        "ai"
        })
    else:
        return jsonify({
            "found":      False,
            "message":    "Ürün listede bulunamadı",
            "ai_raw":     gemini_text,
            "mode":       "ai"
        })


# ──────────────────────────────────────────────
# API: Sağlık Kontrolü
# ──────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":     "ok",
        "products":   len(PRODUCTS),
        "ai_ready":   gemini_client is not None,
        "mode":       "ai" if gemini_client else "demo"
    })


# ──────────────────────────────────────────────
# Ana Giriş
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  SmartCart Urun Tanima Sunucusu")
    print("=" * 50)
    print(f"  Urun sayisi  : {len(PRODUCTS)}")
    print(f"  AI Modu      : {'Aktif' if gemini_client else 'Demo (API key yok)'}")
    print(f"  Sunucu adresi: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
