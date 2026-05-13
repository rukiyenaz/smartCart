import sys, io, numpy as np, cv2
from pathlib import Path
from google import genai
from google.genai import types as gt

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

key = Path(".env").read_text().strip().split("=", 1)[1]
client = genai.Client(api_key=key)

# metadata.csv'den urun adlarini al
names = []
with open("migros_dataset_merged/metadata.csv", encoding="utf-8") as f:
    for line in f.read().split("\n")[1:]:
        if line.strip():
            names.append(line.split(",")[0])

product_list = "\n".join(f"- {n}" for n in names if n)

# Tum Doritos gorsellerini test et
imgs = sorted(Path("migros_dataset_merged").glob("snack_Doritos*.jpg"))
print(f"{len(imgs)} Doritos gorseli bulundu\n")

for img_p in imgs[:5]:
    data  = np.frombuffer(img_p.read_bytes(), dtype=np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

    prompt = (
        "Bu goruntudeki urun hangisi? Sadece asagidaki listeden sec:\n"
        + product_list
        + '\n\nJSON dondur: {"name": "<tam urun adi>"}'
    )

    try:
        resp = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=[
                gt.Part.from_bytes(data=buf.tobytes(), mime_type="image/jpeg"),
                gt.Part.from_text(text=prompt),
            ],
        )
        print(f"Dosya  : {img_p.name}")
        print(f"Yanit  : {resp.text.strip()}\n")
    except Exception as e:
        print(f"HATA   : {e}\n")
