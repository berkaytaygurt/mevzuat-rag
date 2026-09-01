"""Aibars ile ciplak Gemini'yi ayni sorularda karsilastirir.

Sorulan soru: "Bu sistemi kurmak yerine dogrudan Gemini'ye sorsak ne olur?"
Cevabi fikirle degil olcumle veriyoruz.

YONTEM
Kulliyattan somut bir SAYI iceren maddeler seciliyor (sure, oran, tutar).
Her madde icin, cevabi o sayi olan bir soru uretiliyor. Ayni soru:

    A) Ciplak Gemini'ye  -- kaynak verilmeden, kendi bilgisiyle
    B) Aibars'a          -- maddeyi bulup metne dayanarak

Puanlama nesnel: dogru sayi cevapta geciyor mu?

AYRIM ONEMLI
Sorular iki gruba ayriliyor:
    ünlü   -- Kanun (Is Kanunu, TCK, TMK gibi; Gemini bunlari biliyor)
    bilinmeyen -- Teblig, kurum yonetmeligi (Gemini bunlari uydurdugu yer)

Ilk olcumde ciplak Gemini unlu kanunlarda 2/2 dogru, bilinmeyen mevzuatta
0/2 yanlis cikmisti -- ve ikisinde de ayni kendinden emin tonla cevapladi.
Bu betik o gozlemi buyuk ornekle dogrular ya da curutur.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import random
import re
import time

import config
from core import butce

logging.basicConfig(level=logging.ERROR)

# Soru uretirken maddeden alinacak "cevap sayisi" kaliplari
SAYI_RE = re.compile(r"\b(\d{1,6})\b")

SORU_SISTEM = """Sana bir mevzuat maddesi ve içindeki bir sayı verilir.
O sayının cevabı olacağı TEK bir soru yazarsın.

Kurallar:
1. Soru, mevzuatı tam olarak tarif etmeli (hangi kanun/yönetmelik olduğu
   anlaşılmalı) ki kaynaksız da cevaplanabilsin.
2. Cevap yalnızca o sayı olmalı.
3. Tek cümle. Yalnızca soruyu yaz."""

SORU_ISTEM = """Mevzuat: {ad}
Madde {no}: {baslik}

{metin}

Bu metindeki "{sayi}" sayısının cevabı olacağı bir soru yaz."""


def uygun_mu(m: dict) -> bool:
    metin = m.get("metin", "")
    if not (150 < len(metin) < 1200) or m.get("mulga") or not m.get("baslik"):
        return False
    baslik = m["baslik"].lower()
    return not any(k in baslik for k in ("yürürlük", "yürütme", "değiştir"))


def hedef_sayi(metin: str) -> str | None:
    """Maddedeki gercek hukum sayisini secer.

    ILK SURUM BOZUKTU: "en az tekrar eden sayiyi" seciyordu ve mevzuat
    metinlerinde en tekil sayilar degisiklik notlarindaki kanun numaralari
    ("(Degisik: 7/7/2011-646/1 md.)") oldugu icin sorularin neredeyse
    tamami "hangi kanun bu maddeyi degistirdi" sorusuna donusmustu. Bu bir
    hukuk sorusu degil, numara bilgisi; ustelik Aibars o notlari bilerek
    temizledigi icin sistem tam olarak disarida biraktigi seyden sinava
    giriyordu.

    Simdi once degisiklik notlari metinden atiliyor, sonra bir OLCU birimi
    ile birlikte gecen sayilar tercih ediliyor (gun, ay, yil, lira, yuzde).
    Bunlar maddenin gercek hukmunu tasiyan sayilardir.
    """
    # Degisiklik notlarini at: parantez icinde tarih tasiyanlar
    govde = re.sub(r"\([^)]*\d{1,2}/\d{1,2}/\d{4}[^)]*\)", " ", metin)
    govde = re.sub(r"\b\d{1,2}/\d{1,2}/\d{4}\b", " ", govde)

    # Olcu birimi ile birlikte gecen sayilar hukum tasir
    birimli = re.findall(
        r"\b(\d{1,6})\s*(?:gün|ay|yıl|saat|lira|TL|kat|misli|adet|kişi)\b",
        govde, re.IGNORECASE)
    yuzde = re.findall(r"(?:yüzde|%)\s*(\d{1,3})\b", govde, re.IGNORECASE)
    adaylar = birimli + yuzde
    if not adaylar:
        return None

    # Yil gibi gorunenleri ele
    adaylar = [x for x in adaylar if 1 < int(x) < 100000 and not (1900 < int(x) < 2100)]
    if not adaylar:
        return None
    return max(set(adaylar), key=adaylar.count)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=20, help="grup basina soru")
    ap.add_argument("--bekleme", type=float, default=0.5)
    args = ap.parse_args()

    from core.embedder import Embedder
    from core.generate import Generator
    from core.retrieve import Retriever
    from core.vektor import VektorDeposu

    maddeler = json.loads(
        (config.RAW_DIR / "maddeler.json").read_text(encoding="utf-8"))

    gruplar = {
        "ünlü (Kanun)": [m for m in maddeler
                         if m["mevzuat_tur"] == "Kanun" and uygun_mu(m)],
        "bilinmeyen (Tebliğ/Yönetmelik)":
            [m for m in maddeler
             if m["mevzuat_tur"] in ("Teblig", "Kurum ve Kurulus Yonetmeligi",
                                     "Cumhurbaskanligi Yonetmeligi") and uygun_mu(m)],
    }

    random.seed(11)
    uretici = Generator(provider="gemini")
    store = VektorDeposu()
    r = Retriever(store, Embedder())
    cevapci = Generator(provider="gemini")

    anahtar: list[dict] = []
    out = io.StringIO()
    out.write(f"KARSILASTIRMA -- indeks {store.sayi():,} madde\n\n")
    ayrinti = io.StringIO()

    for grup_adi, havuz in gruplar.items():
        # Once olculebilir sayi tasiyanlari suz, SONRA orneklе. Ilk surumde
        # ham havuzdan 60 aday cekiliyordu ve maddelerin yalnizca %3-10'unda
        # boyle bir sayi oldugu icin grup basina 2 soru kaliyordu.
        sayili = [(m, s) for m in havuz if (s := hedef_sayi(m.get("metin", "")))]
        print(f"{grup_adi}: {len(sayili)} uygun madde havuzu", flush=True)
        sorular = []
        for m, sayi in random.sample(sayili, min(len(sayili), args.adet * 2)):
            if len(sorular) >= args.adet:
                break
            try:
                soru = uretici._gemini(
                    SORU_ISTEM.format(ad=m["mevzuat_adi"], no=m["madde_no"],
                                      baslik=m.get("baslik", ""),
                                      metin=m["metin"][:1200], sayi=sayi),
                    sistem=SORU_SISTEM)
            except Exception as exc:
                print(f"soru uretilemedi: {str(exc)[:70]}", flush=True)
                continue
            soru = (soru or "").strip().split("\n")[0]
            if len(soru) < 15:
                continue
            sorular.append((soru, sayi, m))
            time.sleep(args.bekleme)

        ciplak = aibars = 0
        for soru, sayi, m in sorular:
            # A) ciplak Gemini
            try:
                a = uretici._gemini(soru + "\nKısa cevap ver.",
                                    sistem="Sen Türk mevzuatı bilen bir asistansın. "
                                           "Kısa ve net cevap ver.") or ""
            except Exception:
                a = ""
            # B) Aibars
            try:
                bulunan = r.ara(soru, limit=10)
                b = cevapci.cevapla(soru, bulunan) or ""
            except Exception as exc:
                b = f"(hata: {exc})"

            a_ok = sayi in re.sub(r"[.,]", "", a)
            b_ok = sayi in re.sub(r"[.,]", "", b)
            ciplak += a_ok
            aibars += b_ok
            ayrinti.write(f"[{grup_adi}] {soru[:90]}\n")
            ayrinti.write(f"   dogru={sayi}  ciplak={'OK' if a_ok else 'X'}  "
                          f"aibars={'OK' if b_ok else 'X'}\n")
            ayrinti.write(f"   ciplak: {a.strip()[:110]}\n")
            ayrinti.write(f"   aibars: {b.strip()[:110]}\n\n")
            anahtar.append({"grup": grup_adi, "soru": soru, "dogru": sayi,
                            "mevzuat": m["mevzuat_adi"], "madde": m["madde_no"],
                            "ciplak_dogru": a_ok, "aibars_dogru": b_ok})
            time.sleep(args.bekleme)

        n = len(sorular)
        out.write(f"{grup_adi}  ({n} soru)\n")
        out.write(f"  çıplak Gemini : {ciplak}/{n}\n")
        out.write(f"  Aibars        : {aibars}/{n}\n\n")
        with open("karsilastirma.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue() + "\n\n=== AYRINTI ===\n" + ayrinti.getvalue())

    with open("cevap_anahtari.json", "w", encoding="utf-8") as f:
        json.dump(anahtar, f, ensure_ascii=False, indent=1)
    out.write(f"\n{butce.durum()}\n")
    with open("karsilastirma.txt", "w", encoding="utf-8") as f:
        f.write(out.getvalue() + "\n\n=== AYRINTI ===\n" + ayrinti.getvalue())
    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
