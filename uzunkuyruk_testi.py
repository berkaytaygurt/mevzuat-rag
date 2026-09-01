"""Bilinmeyen mevzuatta ciplak Gemini ile Aibars'i karsilastirir.

NEDEN BU TEST
Avukat sorulari testi is hukukunda yapildi ve iki taraf basabas cikti. Ama
is hukuku, dil modelinin EN IYI bildigi alan: 4857 sayili Kanun internette
binlerce kez yazilmis. Kulliyatin asil anlami tersinde -- kimsenin
ezberlemedigi tebligler ve kurum yonetmelikleri.

Kucuk bir on denemede (4 soru) su gorulmustu: unlu kanunlarda Gemini 2/2
dogru, bilinmeyen yonetmeliklerde 0/2 yanlis -- ve ikisinde de ayni
kendinden emin tonla. Bu betik o gozlemi buyuk ornekle sinar.

YONTEM
Teblig / kurum yonetmeligi maddelerinden, icinde OLCU BIRIMLI somut bir
sayi gecenler seciliyor (gun, ay, yil, lira, yuzde). Her madde icin cevabi
o sayi olan bir soru uretiliyor; soru mevzuati acikca tarif ediyor ki
kaynaksiz da cevaplanabilsin.

Puanlama tamamen nesnel: dogru sayi cevapta geciyor mu.

Sorular ayrica sorular_uzunkuyruk.txt dosyasina yaziliyor; ucuncu bir
yanit (Claude) sonradan, dogru cevaplari gormeden eklenebilsin diye.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor

import config
from core import butce

logging.basicConfig(level=logging.ERROR)

SORU_SISTEM = """Sana bir mevzuat maddesi ve içindeki bir sayı verilir.
O sayının cevabı olacağı TEK bir soru yazarsın.

Kurallar:
1. Soru, hangi mevzuattan bahsettiğini AÇIKÇA belirtmeli (tam adıyla) ki
   metni görmeyen biri de cevaplayabilsin.
2. Cevap yalnızca o sayı olmalı.
3. Tek cümle. Yalnızca soruyu yaz, açıklama ekleme."""

SORU_ISTEM = """Mevzuat: {ad}
Madde {no}: {baslik}

{metin}

Bu metindeki "{sayi}" sayısının cevabı olacağı bir soru yaz."""

CIPLAK_SISTEM = ("Sen Türk mevzuatını bilen bir asistansın. Sorulan sayıyı "
                 "kısaca söyle. Bilmiyorsan 'bilmiyorum' de.")


def uygun_mu(m: dict) -> bool:
    metin = m.get("metin", "")
    if not (150 < len(metin) < 1200) or m.get("mulga") or not m.get("baslik"):
        return False
    baslik = m["baslik"].lower()
    return not any(k in baslik for k in ("yürürlük", "yürütme", "değiştir"))


def hedef_sayi(metin: str) -> str | None:
    """Maddedeki gercek hukum sayisini secer.

    Degisiklik notlari once atiliyor: onlardaki kanun numaralari en tekil
    sayilar oldugu icin, filtresiz secim sorulari "hangi kanun bu maddeyi
    degistirdi" trivyasina ceviriyordu.
    """
    govde = re.sub(r"\([^)]*\d{1,2}/\d{1,2}/\d{4}[^)]*\)", " ", metin)
    govde = re.sub(r"\b\d{1,2}/\d{1,2}/\d{4}\b", " ", govde)

    birimli = re.findall(
        r"\b(\d{1,6})\s*(?:gün|ay|yıl|saat|lira|TL|kat|misli|adet|kişi)\b",
        govde, re.IGNORECASE)
    yuzde = re.findall(r"(?:yüzde|%)\s*(\d{1,3})\b", govde, re.IGNORECASE)
    adaylar = [s for s in birimli + yuzde
               if 1 < int(s) < 100000 and not (1900 < int(s) < 2100)]
    if not adaylar:
        return None
    return max(set(adaylar), key=adaylar.count)


def sayi_var_mi(cevap: str, sayi: str) -> bool:
    temiz = re.sub(r"[.,]", "", cevap or "")
    return bool(re.search(rf"\b{re.escape(sayi)}\b", temiz))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=50)
    ap.add_argument("--isci", type=int, default=6)
    args = ap.parse_args()

    from core.embedder import Embedder
    from core.generate import Generator
    from core.retrieve import Retriever
    from core.vektor import VektorDeposu

    maddeler = json.loads(
        (config.RAW_DIR / "maddeler.json").read_text(encoding="utf-8"))
    havuz = [m for m in maddeler
             if m["mevzuat_tur"] in ("Teblig", "Kurum ve Kurulus Yonetmeligi",
                                     "Cumhurbaskanligi Yonetmeligi")
             and uygun_mu(m)]
    sayili = [(m, s) for m in havuz if (s := hedef_sayi(m.get("metin", "")))]
    print(f"havuz: {len(sayili)} uygun madde", flush=True)

    random.seed(23)
    secilen = random.sample(sayili, min(len(sayili), args.adet * 2))
    g = Generator(provider="gemini")
    basla = time.time()

    # --- 1. soru uretimi (paralel) ---
    def soru_uret(ikili):
        m, sayi = ikili
        try:
            s = g._gemini(SORU_ISTEM.format(
                ad=m["mevzuat_adi"], no=m["madde_no"],
                baslik=m.get("baslik", ""), metin=m["metin"][:1100], sayi=sayi),
                sistem=SORU_SISTEM)
        except Exception:
            return None
        s = (s or "").strip().split("\n")[0]
        return (s, sayi, m) if len(s) > 20 else None

    print("1/4 sorular uretiliyor...", flush=True)
    with ThreadPoolExecutor(max_workers=args.isci) as h:
        uretilen = [x for x in h.map(soru_uret, secilen) if x][:args.adet]
    print(f"    {len(uretilen)} soru ({time.time()-basla:.0f} sn)", flush=True)

    with open("sorular_uzunkuyruk.txt", "w", encoding="utf-8") as f:
        for i, (s, _, _) in enumerate(uretilen, 1):
            f.write(f"{i}. {s}\n")

    # --- 2. ciplak Gemini (paralel) ---
    def ciplak(x):
        try:
            return g._gemini(x[0] + "\nSadece sayıyı yaz.",
                             sistem=CIPLAK_SISTEM) or ""
        except Exception as exc:
            return f"(hata: {str(exc)[:50]})"

    print("2/4 ciplak Gemini...", flush=True)
    with ThreadPoolExecutor(max_workers=args.isci) as h:
        ciplak_cevaplar = list(h.map(ciplak, uretilen))
    print(f"    bitti ({time.time()-basla:.0f} sn)", flush=True)

    # --- 3. Aibars (arama sirali, cevap paralel) ---
    print("3/4 Aibars aramalari...", flush=True)
    store = VektorDeposu()
    r = Retriever(store, Embedder())
    bulunanlar = [r.ara(x[0], limit=6) for x in uretilen]

    def aibars(ikili):
        (soru, _, _), bulunan = ikili
        try:
            return g.cevapla(soru, bulunan) or ""
        except Exception as exc:
            return f"(hata: {str(exc)[:50]})"

    with ThreadPoolExecutor(max_workers=args.isci) as h:
        aibars_cevaplar = list(h.map(aibars, list(zip(uretilen, bulunanlar))))
    print(f"    bitti ({time.time()-basla:.0f} sn)", flush=True)

    # --- 4. puanlama ---
    print("4/4 puanlama...", flush=True)
    ciplak_dogru = aibars_dogru = 0
    ciplak_bilmiyorum = aibars_bilmiyorum = 0
    kayit = []
    for (soru, sayi, m), a, b in zip(uretilen, ciplak_cevaplar, aibars_cevaplar):
        ad = sayi_var_mi(a, sayi)
        bd = sayi_var_mi(b, sayi)
        ciplak_dogru += ad
        aibars_dogru += bd
        if "bilmiyorum" in (a or "").lower():
            ciplak_bilmiyorum += 1
        if "bulamadım" in (b or "").lower():
            aibars_bilmiyorum += 1
        kayit.append({"soru": soru, "dogru": sayi,
                      "mevzuat": m["mevzuat_adi"], "madde": m["madde_no"],
                      "ciplak": a, "aibars": b,
                      "ciplak_dogru": ad, "aibars_dogru": bd})

    n = len(uretilen)
    o = io.StringIO()
    o.write(f"UZUN KUYRUK TESTI -- {n} soru, {time.time()-basla:.0f} saniye\n")
    o.write("(teblig ve kurum yonetmelikleri; cevap somut bir sayi)\n\n")
    o.write(f"{'':<18}{'dogru':>8}{'oran':>9}{'bilmiyorum':>13}\n")
    o.write("-" * 50 + "\n")
    o.write(f"{'çıplak Gemini':<18}{ciplak_dogru:>6}/{n}{100*ciplak_dogru/n:>8.0f}%"
            f"{ciplak_bilmiyorum:>10}\n")
    o.write(f"{'Aibars':<18}{aibars_dogru:>6}/{n}{100*aibars_dogru/n:>8.0f}%"
            f"{aibars_bilmiyorum:>10}\n")
    o.write(f"\n{butce.durum()}\n")
    with open("uzunkuyruk_testi.txt", "w", encoding="utf-8") as f:
        f.write(o.getvalue())
    with open("uzunkuyruk_testi.json", "w", encoding="utf-8") as f:
        json.dump(kayit, f, ensure_ascii=False, indent=1)
    store.close()
    print(o.getvalue(), flush=True)


if __name__ == "__main__":
    main()
