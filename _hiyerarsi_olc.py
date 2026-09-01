"""Normlar hiyerarsisi carpanini uc olcum setinde tarar.

TETIKLEYEN GOZLEM
"Kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir?" sorusunda
kurali koyan madde (1475 sayili Kanun m.14) 8. sirada kaliyor ve onune
sunlar geciyor:

    1. BOTAS personel yonetmeligi m.53
    2. Turkiye Petrolleri personel yonetmeligi m.15
    3. Turkiye Petrolleri personel yonetmeligi m.47

Ucu de kidem tazminatindan BAHSEDIYOR ama hicbiri kurali koymuyor. Mevcut
hiyerarsi carpani kanuna 1.00, kurum yonetmeligine 0.88 veriyor -- yalnizca
%12 fark. Kulliyat 275 bin maddeye cikinca bu fark yetmiyor: bir soruya
benzeyen yuzlerce kurum duzenlemesi var, kanun ise tek.

Bu betik carpanin ne kadar sertlestirilecegini olcerek belirler.
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

# Denenecek hiyerarsi tablolari: mevcut, orta, sert
TABLOLAR = {
    "mevcut": {"Kanun": 1.00, "Cumhurbaskanligi Kararnamesi": 0.97,
               "Kanun Hukmunde Kararname": 0.97, "Tuzuk": 0.94,
               "Cumhurbaskanligi Yonetmeligi": 0.91, "Yonetmelik": 0.91,
               "Kurum ve Kurulus Yonetmeligi": 0.88, "Teblig": 0.85},
    "orta":   {"Kanun": 1.00, "Cumhurbaskanligi Kararnamesi": 0.92,
               "Kanun Hukmunde Kararname": 0.92, "Tuzuk": 0.88,
               "Cumhurbaskanligi Yonetmeligi": 0.80, "Yonetmelik": 0.80,
               "Kurum ve Kurulus Yonetmeligi": 0.70, "Teblig": 0.70},
    "sert":   {"Kanun": 1.00, "Cumhurbaskanligi Kararnamesi": 0.88,
               "Kanun Hukmunde Kararname": 0.88, "Tuzuk": 0.82,
               "Cumhurbaskanligi Yonetmeligi": 0.68, "Yonetmelik": 0.68,
               "Kurum ve Kurulus Yonetmeligi": 0.55, "Teblig": 0.55},
}

# Kurali koyan maddenin kacinci sirada geldigi izlenen ornek
ORNEK = ("Kıdem tazminatına hak kazanmak için en az ne kadar çalışmak gerekir?",
         "1475", "14")


def sira(sonuclar, kanun, madde):
    for i, m in enumerate(sonuclar, 1):
        if m.get("mevzuat_no") == kanun and (madde is None or m.get("madde_no") == madde):
            return i
    return None


def olc(r, sorular):
    s = [sira(r.ara(q, limit=10), k, m) for q, k, m in sorular]
    n = len(s)
    return (sum(1 for x in s if x == 1), sum(1 for x in s if x and x <= 5),
            sum(1 / x for x in s if x) / n)


def main() -> None:
    setler = [("el", EL), ("yerel", YEREL[:YEREL_KAC]), ("gemini", GEMINI)]
    store, emb = VektorDeposu(), Embedder()
    out = io.StringIO()
    baslik = f"{'tablo':>8}"
    for ad, s in setler:
        baslik += f" | {ad}({len(s)}) ilk1 ilk5   MRR"
    baslik += " | kıdem sırası"
    out.write(baslik + "\n" + "-" * len(baslik) + "\n")

    import core.reranker as rr
    for ad, tablo in TABLOLAR.items():
        rr._HIYERARSI = tablo
        config.HIYERARSI = True
        r = Retriever(store, emb)
        r.ara("isinma", limit=5)
        satir = f"{ad:>8}"
        for _, sorular in setler:
            a = olc(r, sorular)
            satir += f" | {a[0]:>9}{a[1]:>5}{a[2]:>6.3f}"
        yer = sira(r.ara(ORNEK[0], limit=30), ORNEK[1], ORNEK[2])
        satir += f" | {yer if yer else '30+'}"
        out.write(satir + "\n")
        with open("hiyerarsi_olcum.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue())

    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
