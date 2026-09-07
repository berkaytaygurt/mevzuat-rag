"""Kulliyat kapsam denetimi: katalogdaki her kanunun maddeler.json'da fiilen
var olup olmadigini kontrol eder.

Neden bu script var: maddeler.json (~377 MB) ve data/index_karar/kayitlar.json
(~398 MB) bulut ortamina aktarilamayacak kadar buyuk (aktarim zaman asimina
ugradi). Bu yuzden kapsam denetimi -- 916 kanunun kacinin gercekten
maddeler.json icinde madde icerdigi -- yerelde calistirilmali.

Kullanim (proje kok dizininde, .venv aktifken):
    python kapsam_denetim.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
katalog = json.loads((ROOT / "data" / "raw" / "katalog.json").read_text(encoding="utf-8"))
maddeler_yolu = ROOT / "data" / "raw" / "maddeler.json"

print(f"Katalogdaki toplam kayit: {len(katalog)}")
tur_sayisi = Counter(k.get("tur_adi") for k in katalog)
for tur, n in tur_sayisi.most_common():
    print(f"  {tur:35s} {n}")

print("\nmaddeler.json okunuyor (buyuk dosya, biraz surebilir)...")
maddeler = json.loads(maddeler_yolu.read_text(encoding="utf-8"))
print(f"Toplam madde kaydi: {len(maddeler)}")

madde_sayisi_no = defaultdict(int)
for m in maddeler:
    no = m.get("mevzuat_no")
    if no:
        madde_sayisi_no[no] += 1

print(f"maddeler.json icinde en az 1 maddesi olan mevzuat sayisi: {len(madde_sayisi_no)}")

# Katalogdaki her turden, hic maddesi olmayanlari say
print("\n--- Tur bazinda kapsam (katalogdaki kayit vs maddeler.json'da en az 1 maddesi olan) ---")
by_tur = defaultdict(list)
for k in katalog:
    by_tur[k.get("tur_adi")].append(k.get("mevzuat_no"))

eksik_kanunlar = []
for tur, numaralar in by_tur.items():
    toplam = len(numaralar)
    var_olan = sum(1 for no in numaralar if madde_sayisi_no.get(no, 0) > 0)
    eksik = toplam - var_olan
    print(f"{tur:35s} toplam {toplam:5d}  maddesi-var {var_olan:5d}  eksik {eksik:5d}")
    if tur == "Kanun":
        for no in numaralar:
            if madde_sayisi_no.get(no, 0) == 0:
                ad = next((k.get("ad") for k in katalog if k.get("mevzuat_no") == no), "?")
                eksik_kanunlar.append((no, ad))

if eksik_kanunlar:
    print(f"\nMaddesi hic olmayan {len(eksik_kanunlar)} kanun:")
    for no, ad in eksik_kanunlar:
        print(f"  {no}  {ad}")

# Cok az maddesi olan kanunlar (muhtemelen kesik/eksik ayristirma)
print("\n--- 3 veya daha az maddesi olan kanunlar (supheli, muhtemelen kesik) ---")
for k in katalog:
    if k.get("tur_adi") != "Kanun":
        continue
    n = madde_sayisi_no.get(k.get("mevzuat_no"), 0)
    if 0 < n <= 3:
        print(f"  {k.get('mevzuat_no')}  {n} madde  {k.get('ad')}")
