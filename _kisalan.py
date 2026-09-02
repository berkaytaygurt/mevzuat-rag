import json, logging, random, sys
sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)
import config
from scraper.client import MevzuatClient
from scraper.parser import parse_pdf
kayitlar = json.loads((config.RAW_DIR / "maddeler.json").read_text(encoding="utf-8"))
gruplar = {}
for k in kayitlar:
    if k.get("mevzuat_tur") == "Kanun":
        gruplar.setdefault((k["mevzuat_no"], k["tertip"]), []).append(k)
adaylar = [g for g, v in gruplar.items() if len(v) >= 20]
random.seed(7); secim = random.sample(adaylar, 30)
c = MevzuatClient(delay=0.6)
bulunan = 0
for no, tertip in secim:
    eski = {str(k["madde_no"]): k for k in gruplar[(no, tertip)]}
    try:
        yeni = {m.madde_no: m for m in parse_pdf(c.mevzuat_pdf(1, no, tertip),
                tur_adi="Kanun", mevzuat_no=no, tertip=tertip)}
    except Exception:
        continue
    for a in sorted(set(eski) & set(yeni)):
        e, y = eski[a]["metin"], yeni[a].metin
        if len(y) < len(e) * 0.75 and len(e) > 150:
            bulunan += 1
            if bulunan <= 8:
                print(f"SONUC === {no} m.{a}  {len(e)} -> {len(y)}", flush=True)
                print(f"SONUC ESKI: {e[:260]}", flush=True)
                print(f"SONUC YENI: {y[:260]}", flush=True)
print("SONUC toplam %25+ kisalan madde:", bulunan)
