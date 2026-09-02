"""Gemini'yi INTERNET ARAMASI ACIKKEN olcer.

NEDEN
Onceki uzun kuyruk testinde Gemini yalnizca hafizasindan cevapladi ve
bilinmeyen mevzuatta %57'de kaldi. Ama gercek rakip bu degil: arama
verilmis bir dil modeli mevzuat.gov.tr'ye bakip metni bulabilir -- yani
kabaca bizim yaptigimiz isi yapar, sadece bizim indeksimiz yerine
Google'in indeksiyle.

Bu betik ayni 50 soruyu arama acikken sorar. Sorular ve dogru cevaplar
uzunkuyruk_testi.json'dan okunur, yani karsilastirma birebir ayni sette.

Sonuc uc sutunlu olur:
    Gemini (hafizadan)  -- onceki olcum
    Gemini (aramali)    -- bu olcum
    Aibars              -- onceki olcum
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

import config
from core import butce

logging.basicConfig(level=logging.ERROR)


def sayi_var_mi(cevap: str, sayi: str) -> bool:
    temiz = re.sub(r"[.,]", "", cevap or "")
    return bool(re.search(rf"\b{re.escape(sayi)}\b", temiz))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--isci", type=int, default=5)
    args = ap.parse_args()

    from google import genai
    from google.genai import types

    kayit = json.loads(
        (config.ROOT / "uzunkuyruk_testi.json").read_text(encoding="utf-8"))
    c = genai.Client(api_key=config.GEMINI_API_KEY)
    ayar = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())])
    basla = time.time()

    def aramali(x) -> str:
        try:
            butce.izin_iste()
            r = c.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=x["soru"] + "\nSadece sayıyı yaz.", config=ayar)
            k = getattr(r, "usage_metadata", None)
            butce.kaydet(getattr(k, "prompt_token_count", 0) or 0,
                         getattr(k, "candidates_token_count", 0) or 0)
            return r.text or ""
        except Exception as exc:
            return f"(hata: {str(exc)[:60]})"

    print(f"{len(kayit)} soru, arama acik...", flush=True)
    with ThreadPoolExecutor(max_workers=args.isci) as h:
        cevaplar = list(h.map(aramali, kayit))
    print(f"bitti ({time.time()-basla:.0f} sn)", flush=True)

    hafiza = aramayla = aibars = hata = 0
    for x, a in zip(kayit, cevaplar):
        if a.startswith("(hata"):
            hata += 1
            continue
        hafiza += x["ciplak_dogru"]
        aibars += x["aibars_dogru"]
        aramayla += sayi_var_mi(a, x["dogru"])
        x["aramali"] = a
        x["aramali_dogru"] = sayi_var_mi(a, x["dogru"])

    n = len(kayit) - hata
    o = io.StringIO()
    o.write(f"ARAMALI KARSILASTIRMA -- {n} soru (teknik hata: {hata})\n")
    o.write("(teblig ve kurum yonetmelikleri; cevap somut bir sayi)\n\n")
    o.write(f"{'':<26}{'dogru':>8}{'oran':>8}\n" + "-" * 44 + "\n")
    for ad, d in (("Gemini (hafizadan)", hafiza),
                  ("Gemini (arama acik)", aramayla),
                  ("Aibars", aibars)):
        o.write(f"{ad:<26}{d:>5}/{n}{100*d/n:>7.0f}%\n")
    o.write(f"\n{butce.durum()}\n")

    with open("aramali_test.txt", "w", encoding="utf-8") as f:
        f.write(o.getvalue())
    with open("uzunkuyruk_testi.json", "w", encoding="utf-8") as f:
        json.dump(kayit, f, ensure_ascii=False, indent=1)
    print(o.getvalue())


if __name__ == "__main__":
    main()
