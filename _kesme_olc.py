"""Dipnot duzeltmesinin kulliyata kazandiracagini ornekle olcer."""
import json, logging, random, sys
sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)
import config
from scraper.client import MevzuatClient
from scraper.parser import parse_pdf

MADDE_YOLU = config.RAW_DIR / "maddeler.json"
kayitlar = json.loads(MADDE_YOLU.read_text(encoding="utf-8"))

# Kanunlari (tur=Kanun) grupla
gruplar = {}
for k in kayitlar:
    if k.get("mevzuat_tur") != "Kanun":
        continue
    gruplar.setdefault((k["mevzuat_no"], k["tertip"]), []).append(k)

# En az 20 maddeli kanunlardan 30 tanesini rastgele sec
adaylar = [g for g, v in gruplar.items() if len(v) >= 20]
random.seed(7)
secim = random.sample(adaylar, 30)

c = MevzuatClient(delay=0.6)
t_eski = t_yeni = 0
buyuyen = kisa_eski = kisa_yeni = basarisiz = 0
for no, tertip in secim:
    eski = {str(k["madde_no"]): k for k in gruplar[(no, tertip)]}
    try:
        ham = c.mevzuat_pdf(1, no, tertip)
        yeni = {m.madde_no: m for m in parse_pdf(
            ham, tur_adi="Kanun", mevzuat_no=no, tertip=tertip)}
    except Exception as exc:
        print(f"SONUC HATA {no}: {str(exc)[:60]}", flush=True); basarisiz += 1; continue
    if not yeni:
        print(f"SONUC BOS {no}", flush=True); basarisiz += 1; continue

    ortak = set(eski) & set(yeni)
    e = sum(len(eski[a]["metin"]) for a in ortak)
    y = sum(len(yeni[a].metin) for a in ortak)
    b = sum(1 for a in ortak if len(yeni[a].metin) > len(eski[a]["metin"]) * 1.15)
    t_eski += e; t_yeni += y; buyuyen += b
    kisa_eski += sum(1 for a in ortak
                     if len(eski[a]["metin"]) < 120 and not eski[a].get("mulga"))
    kisa_yeni += sum(1 for a in ortak
                     if len(yeni[a].metin) < 120 and not yeni[a].mulga)
    print(f"SONUC {no:>6} t{tertip} | ortak {len(ortak):>4} | "
          f"karakter {e:>7} -> {y:>7} (%{(y/e-1)*100:+.1f}) | buyuyen {b}",
          flush=True)

print(f"SONUC ---")
print(f"SONUC basarisiz kanun: {basarisiz}/30")
print(f"SONUC toplam karakter: {t_eski} -> {t_yeni} (%{(t_yeni/t_eski-1)*100:+.1f})")
print(f"SONUC uzunlugu %15+ artan madde: {buyuyen}")
print(f"SONUC kisa(<120) mulga-degil madde: {kisa_eski} -> {kisa_yeni}")
