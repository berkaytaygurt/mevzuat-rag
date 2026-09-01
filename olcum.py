"""Arama isabetini olcer.

    .venv\\Scripts\\python olcum.py            # mevcut ayarla
    .venv\\Scripts\\python olcum.py --rerank   # yeniden siralama acik

Olculen degerler:
  ilk-1 / ilk-3 / ilk-5 : dogru maddenin ilk N sonuc icinde cikma orani
  MRR                   : dogru sonucun sira degerinin tersinin ortalamasi
                          (1. sirada 1.00, 2. sirada 0.50, 3. sirada 0.33)

MRR tek basina en bilgilendirici olan; "ilk 5'te var" demek, 5. sirada olmakla
1. sirada olmak arasindaki farki gizler.
"""
from __future__ import annotations

import argparse
import io
import logging
import time

from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_seti import SORULAR

logging.basicConfig(level=logging.ERROR)


def sira_bul(sonuclar: list[dict], kanun: str, madde: str | None) -> int | None:
    """Dogru sonucun kacinci sirada oldugunu doner (1'den baslar)."""
    for i, m in enumerate(sonuclar, 1):
        if m.get("mevzuat_no") != kanun:
            continue
        if madde is None or m.get("madde_no") == madde:
            return i
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerank", action="store_true", help="yeniden siralamayi ac")
    ap.add_argument("--limit", type=int, default=5, help="dondurulen sonuc sayisi")
    ap.add_argument("--cikti", default=None, help="sonucun yazilacagi dosya")
    ap.add_argument("--ascii", action="store_true",
                    help="sorulari Turkce karakter kullanmadan sor")
    ap.add_argument("--sentetik", action="store_true",
                    help="405 soruluk sentetik seti kullan")
    ap.add_argument("--kac", type=int, default=None, help="ilk N soru")
    args = ap.parse_args()

    global SORULAR
    if args.sentetik:
        from tests.olcum_sentetik import SORULAR as SENTETIK
        SORULAR = SENTETIK
    if args.kac:
        SORULAR = SORULAR[:args.kac]
    if args.ascii:
        from tests.olcum_ascii import SORULAR as ASCII_SORULAR
        SORULAR = ASCII_SORULAR

    store = VektorDeposu()
    retriever = Retriever(store, Embedder(), rerank=args.rerank)

    out = io.StringIO()
    basligi = ("YENIDEN SIRALAMA ACIK" if args.rerank else "TEMEL")
    basligi += " | ASCII sorgu" if args.ascii else " | aksanli sorgu"
    out.write(f"{basligi}\n{'=' * 78}\n")
    out.write(f"{'sira':>5}  {'soru':<44} {'beklenen':<14} bulunan\n")
    out.write("-" * 78 + "\n")

    siralar: list[int | None] = []
    basla = time.time()

    for soru, kanun, madde in SORULAR:
        sonuclar = retriever.ara(soru, limit=args.limit)
        sira = sira_bul(sonuclar, kanun, madde)
        siralar.append(sira)

        ilk = sonuclar[0] if sonuclar else {}
        bulunan = f"{ilk.get('mevzuat_no', '-')} m.{ilk.get('madde_no', '-')}"
        beklenen = f"{kanun} m.{madde}" if madde else f"{kanun} (kanun)"
        isaret = str(sira) if sira else "yok"
        out.write(f"{isaret:>5}  {soru[:44]:<44} {beklenen:<14} {bulunan}\n")

    sure = time.time() - basla
    store.close()

    n = len(siralar)
    ilk1 = sum(1 for s in siralar if s == 1)
    ilk3 = sum(1 for s in siralar if s and s <= 3)
    ilk5 = sum(1 for s in siralar if s and s <= 5)
    mrr = sum(1 / s for s in siralar if s) / n

    out.write("-" * 78 + "\n")
    out.write(f"soru sayisi : {n}\n")
    out.write(f"ilk-1       : {ilk1}/{n}  (%{100 * ilk1 / n:.0f})\n")
    out.write(f"ilk-3       : {ilk3}/{n}  (%{100 * ilk3 / n:.0f})\n")
    out.write(f"ilk-5       : {ilk5}/{n}  (%{100 * ilk5 / n:.0f})\n")
    out.write(f"MRR         : {mrr:.3f}\n")
    out.write(f"sure        : {sure:.1f} sn ({sure / n:.2f} sn/soru)\n")

    metin = out.getvalue()
    print(metin)
    if args.cikti:
        with open(args.cikti, "w", encoding="utf-8") as f:
            f.write(metin)


if __name__ == "__main__":
    main()
