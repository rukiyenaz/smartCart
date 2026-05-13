import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def normalize(text):
    for k, v in [("ı","i"),("İ","I"),("ş","s"),("Ş","S"),("ğ","g"),("Ğ","G"),
                 ("ü","u"),("Ü","U"),("ö","o"),("Ö","O"),("ç","c"),("Ç","C")]:
        text = text.replace(k, v)
    return text.lower()

PRODUCTS = [
    {"name": "Doritos Storm Flamin Hot Süper Boy 125 G"},
    {"name": "Doritos Storm Bi Tık Acı Süper Boy 125 G"},
    {"name": "Doritos Nacho Süper Boy 130 G"},
    {"name": "Eti Crax Çubuk Kraker 40 G"},
]

# Kameradan gelebilecek tipik yanıtlar
raw_texts = [
    '{"name": "Doritos"}',
    '{"name": "Doritos Storm"}',
    '{"name": "Doritos Storm Flamin Hot"}',
    '{"name": "Doritos Storm Flamin Hot Super Boy 125g"}',
    "Doritos cipsi",
    '{"name": null}',
]

def match(raw):
    candidates = []
    m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group())
            for k in ("name", "product"):
                if k in obj and obj[k]:
                    candidates.append(str(obj[k]))
        except Exception:
            pass
    for line in raw.split("\n"):
        line = line.strip().strip("-*").strip()
        if 3 < len(line) < 120:
            candidates.append(line)

    norm_cands = [normalize(c) for c in candidates]
    best, best_score = None, 0.0
    for prod in PRODUCTS:
        p_norm = normalize(prod["name"])
        p_tokens = set(p_norm.split())
        for c in norm_cands:
            c_tokens = set(c.split())
            if not c_tokens:
                continue
            common = p_tokens & c_tokens
            if not common:
                continue
            score = len(common) / max(len(p_tokens), len(c_tokens))
            if p_norm in c or c in p_norm:
                score += 0.5
            if score > best_score:
                best_score = score
                best = prod

    found = best["name"] if best and best_score >= 0.3 else "TANINAMADI"
    return best_score, found

print("MEVCUT ALGORİTMA TEST:\n")
for raw in raw_texts:
    score, found = match(raw)
    status = "OK" if found != "TANINAMADI" else "FAIL"
    print(f"[{status}] Girdi: {raw[:45]:48s} | Skor: {score:.2f} | {found}")
