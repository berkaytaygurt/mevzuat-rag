"""Birinci asamanin tavanini olcer.

Cross-encoder yalnizca onune gelen adaylari siralayabilir. Dogru madde ilk
asamanin aday havuzuna hic girmiyorsa, yeniden siralama da onu kurtaramaz.
Bu olcum, cabayi nereye yatiracagimizi soyler:

  - Tavan yuksek, isabet dusukse  -> sorun siralamada, reranker'a yatirim yap
  - Tavan da dusukse             -> sorun aramada, aday havuzunu genislet
                                    veya embedding/BM25 tarafini duzelt
"""
from __future__ import annotations

import io
import logging

from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_ascii import SORULAR as ASCII_SORULAR
from tests.olcum_seti import SORULAR

logging.basicConfig(level=logging.ERROR)

PENCERELER = [5, 12, 25, 50, 100]


def sira(sonuclar, kanun, madde):
    for i, m in enumerate(sonuclar, 1):
        if m.get("mevzuat_no") == kanun and (madde is None or m.get("madde_no") == madde):
            return i
    return None


def main() -> None:
    store = VektorDeposu()
    # Yeniden siralama KAPALI: saf birinci asamanin ne getirdigini olcuyoruz
    r = Retriever(store, Embedder(), rerank=False)

    out = io.StringIO()
    for etiket, sorular in (("AKSANLI", SORULAR), ("ASCII", ASCII_SORULAR)):
        out.write(f"\n{etiket} sorgular — birinci asama tavani\n")
        out.write(f"{'pencere':>9}{'bulunan':>10}{'oran':>8}\n")
        out.write("-" * 28 + "\n")
        for p in PENCERELER:
            bulunan = 0
            for soru, kanun, madde in sorular:
                s = r.ara(soru, limit=p, aday=max(p, 100))
                if sira(s, kanun, madde):
                    bulunan += 1
            out.write(f"{p:>9}{bulunan:>7}/{len(sorular)}"
                      f"{100 * bulunan / len(sorular):>7.0f}%\n")

    # Hangi sorular en genis pencerede bile bulunamiyor?
    out.write("\n=== 100 adayda BILE bulunamayanlar (aksanli) ===\n")
    for soru, kanun, madde in SORULAR:
        s = r.ara(soru, limit=100, aday=150)
        if not sira(s, kanun, madde):
            out.write(f"   {soru[:52]:<54} -> {kanun} m.{madde}\n")

    store.close()
    metin = out.getvalue()
    print(metin)
    with open("tavan.txt", "w", encoding="utf-8") as f:
        f.write(metin)


if __name__ == "__main__":
    main()
