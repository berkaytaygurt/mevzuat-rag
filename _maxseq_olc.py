"""Yeniden siralayicinin gordugu metin uzunlugunun etkisi.

Olculen sorun: RERANK_MAX_SEQ=256 token, yani cross-encoder maddenin ilk
~768 karakterini goruyor. Kulliyatta 58.975 madde (%34) bundan uzun.
Basarisiz ornekteki madde (1475 m.14, kidem tazminati) 2.002 karakter --
siralayici onun yalnizca %38'ini goruyor.

Bedeli: uzun dizi hem yavas hem VRAM yiyor (4 GB kart). Yigin boyutu
dusurulerek dengeleniyor. Sure de olculuyor; kazanc suredeki artisi hak
etmiyorsa uygulanmayacak.
"""
from __future__ import annotations

import io
import logging
import time

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
    t = time.time()
    s = [sira(r.ara(q, limit=10), k, m) for q, k, m in sorular]
    n = len(s)
    return (sum(1 for x in s if x == 1), sum(1 for x in s if x and x <= 5),
            sum(1 / x for x in s if x) / n, (time.time() - t) / n)


def main() -> None:
    setler = [("el", EL), ("yerel", YEREL[:YEREL_KAC]), ("gemini", GEMINI)]
    store, emb = VektorDeposu(), Embedder()
    out = io.StringIO()
    baslik = f"{'max_seq':>8}{'yigin':>7}"
    for ad, s in setler:
        baslik += f" | {ad}({len(s)}) ilk1  ilk5    MRR"
    baslik += " |    sure"
    out.write(baslik + "\n" + "-" * len(baslik) + "\n")

    # (max_seq, batch) -- uzun dizide yigin kucultuluyor, 4 GB VRAM sinirli
    for max_seq, yigin in ((256, 12), (384, 8), (512, 6)):
        config.RERANK_MAX_SEQ, config.RERANK_BATCH = max_seq, yigin
        r = Retriever(store, emb)
        r.ara("isinma", limit=5)
        satir = f"{max_seq:>8}{yigin:>7}"
        sureler = []
        for _, sorular in setler:
            a = olc(r, sorular)
            satir += f" | {a[0]:>10}{a[1]:>6}{a[2]:>7.3f}"
            sureler.append(a[3])
        satir += f" | {sum(sureler)/len(sureler):>5.2f}sn"
        out.write(satir + "\n")
        with open("maxseq_olcum.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue())

    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
