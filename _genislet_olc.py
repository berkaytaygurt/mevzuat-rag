"""Sorgu genisletmenin uc olcum setinde etkisi.

Fikir: kullanici gundelik dille yazar, kanun hukuk diliyle yazilmistir.
Sorguyu once Gemini'ye verip hukuk terimlerine cevirir, sonra ararız.

    "isten atildim param ne olur"
      -> "kidem tazminati, ihbar tazminati, is sozlesmesinin feshi"

Bu, olculen en buyuk zayifligi hedefliyor: dogal yazilmis sorularda isabet
%68'den %23'e dusuyordu.

Genisletme UYARLAMALI calisir -- her sorguda degil, yalnizca ilk arama zayif
sonuc verdiginde. Bu yuzden Gemini cagrisi sayisi soru sayisindan az olur.
Maliyet sayaci butce modulunde tutuluyor.
"""
from __future__ import annotations

import io
import logging
import time

import config
from core import butce
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
    t = time.time()
    s = [sira(r.ara(q, limit=10), k, m) for q, k, m in sorular]
    n = len(s)
    return (sum(1 for x in s if x == 1), sum(1 for x in s if x and x <= 5),
            sum(1 / x for x in s if x) / n, (time.time() - t) / n)


def main() -> None:
    setler = [("el", EL), ("yerel", YEREL[:YEREL_KAC]), ("gemini", GEMINI)]
    store, emb = VektorDeposu(), Embedder()
    out = io.StringIO()
    out.write(f"indeks: {store.sayi():,} madde\n\n")
    baslik = f"{'genislet':>11}"
    for ad, s in setler:
        baslik += f" | {ad}({len(s)}) ilk1  ilk5    MRR"
    baslik += " |   sure |    maliyet"
    out.write(baslik + "\n" + "-" * len(baslik) + "\n")

    # (genisletme, her sorguda mi) -- ucuncu satir fikri gercekten test eder:
    # uyarlamali kipte 448 sorgunun yalnizca 28'inde tetiklenmisti.
    # Yalnizca test edilmemis ayar olculuyor: KAPALI ve UYARLAMALI
    # daha once olculdu (data/yedek/genislet_uyarlamali.txt), tekrari
    # 15 dakika bosa harciyor.
    for etiket, acik, hep in (("HER SORGU", True, True),):
        config.SORGU_GENISLET, config.GENISLET_HEP = acik, hep
        onceki = butce.bugun()["istek"]
        r = Retriever(store, emb)
        r.ara("isinma", limit=5)
        satir = f"{etiket:>11}"
        sureler = []
        for _, sorular in setler:
            a = olc(r, sorular)
            satir += f" | {a[0]:>10}{a[1]:>6}{a[2]:>7.3f}"
            sureler.append(a[3])
        istek = butce.bugun()["istek"] - onceki
        satir += (f" | {sum(sureler)/len(sureler):>4.1f}sn | "
                  f"{istek:>4} istek, {butce.tahmini_maliyet():.3f}$")
        out.write(satir + "\n")
        with open("genislet_olcum.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue())

    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
