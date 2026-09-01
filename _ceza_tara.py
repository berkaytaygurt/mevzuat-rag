"""Ek/Gecici madde cezasini UC olcum setinde birden tarar.

Neden uc set: tek sette olculen fark gurultu cikabiliyor. Bugun 34 soruluk
sette "kazanc" gorunen bir ayar 150 soruluk sette tersine dondu.

    el seti   34 soru, elle yazildi, cevabi kulliyatta dogrulandi
    yerel    405 soru, yerel 3B model uretti -- cogu bozuk dilbilgisi
    gemini    40 soru, Gemini uretti -- dogal Turkce, en temsili ama kucuk

Tetikleyen gozlem: "kidem tazminatina hak kazanmak icin ne kadar calismak
gerekir" sorusunda dogru madde (1475 m.14) 21. siraya dusuyor ve one
"Gecici 11" gibi maddeler geciyor. Ayni sorunun anahtar kelime hali
("kidem tazminati sartlari") 1. sirayi veriyor.
"""
from __future__ import annotations

import io
import logging

import config
from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_seti import SORULAR as EL
from tests.olcum_sentetik import SORULAR as YEREL
from tests.olcum_gemini import SORULAR as GEMINI

logging.basicConfig(level=logging.ERROR)
YEREL_KAC = 150


def sira(sonuclar, kanun, madde):
    for i, m in enumerate(sonuclar, 1):
        if m.get("mevzuat_no") == kanun and (madde is None or m.get("madde_no") == madde):
            return i
    return None


def olc(r, sorular):
    s = [sira(r.ara(q, limit=10), k, m) for q, k, m in sorular]
    n = len(s)
    return (sum(1 for x in s if x == 1), sum(1 for x in s if x and x <= 5),
            sum(1 / x for x in s if x) / n, n)


def main() -> None:
    setler = [("el", EL), ("yerel", YEREL[:YEREL_KAC]), ("gemini", GEMINI)]
    store, emb = VektorDeposu(), Embedder()
    out = io.StringIO()
    baslik = f"{'ceza':>6}"
    for ad, s in setler:
        baslik += f" | {ad}({len(s)}) ilk1  ilk5    MRR"
    out.write(baslik + "\n" + "-" * len(baslik) + "\n")

    for ceza in (0.00, 0.05, 0.20, 0.40):
        config.EK_MADDE_CEZASI = ceza
        r = Retriever(store, emb)
        r.ara("isinma", limit=5)
        satir = f"{ceza:>6.2f}"
        for _, sorular in setler:
            a = olc(r, sorular)
            satir += f" | {a[0]:>10}{a[1]:>6}{a[2]:>7.3f}"
        out.write(satir + "\n")
        with open("ceza_tarama.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue())

    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
