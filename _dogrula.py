"""34 soruluk sette bulunan ayarlari 405 soruluk sentetik sette dogrular.

Amac: kucuk sette olculen kazanclarin gercek mi gurultu mu oldugunu anlamak.
Ayni siralama iki sette de cikiyorsa kazanc gercektir.
"""
from __future__ import annotations

import io
import logging
import time

import config
from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_sentetik import SORULAR

logging.basicConfig(level=logging.ERROR)

KAC = 150          # tam set 405; 150 soru yeterli ayrim gucu veriyor


def sira(sonuclar, kanun, madde):
    for i, m in enumerate(sonuclar, 1):
        if m.get("mevzuat_no") == kanun and (madde is None or m.get("madde_no") == madde):
            return i
    return None


def olc(r, sorular):
    siralar = [sira(r.ara(s, limit=10), k, m) for s, k, m in sorular]
    n = len(siralar)
    return {
        "ilk1": sum(1 for s in siralar if s == 1),
        "ilk5": sum(1 for s in siralar if s and s <= 5),
        "ilk10": sum(1 for s in siralar if s),
        "mrr": sum(1 / s for s in siralar if s) / n,
        "n": n,
    }


def main() -> None:
    sorular = SORULAR[:KAC]
    store = VektorDeposu()
    emb = Embedder()
    out = io.StringIO()
    out.write(f"SENTETIK SET ({len(sorular)} soru)\n")
    out.write(f"{'ayar':<26}{'ilk-1':>9}{'ilk-5':>9}{'MRR':>8}{'sure':>9}\n")
    out.write("-" * 62 + "\n")

    denemeler = [
        ("aday=25, agirlik=0.8", 25, 0.8),
        ("aday=50, agirlik=0.8", 50, 0.8),
        ("aday=50, agirlik=0.9", 50, 0.9),
        ("aday=50, agirlik=1.0", 50, 1.0),
    ]
    for ad, aday, agirlik in denemeler:
        config.RERANK_ADAY, config.RERANK_AGIRLIK = aday, agirlik
        r = Retriever(store, emb)
        r.ara("isinma", limit=5)
        t = time.time()
        s = olc(r, sorular)
        sure = (time.time() - t) / s["n"]
        out.write(f"{ad:<26}{s['ilk1']:>6}/{s['n']}{s['ilk5']:>6}/{s['n']}"
                  f"{s['mrr']:>8.3f}{sure:>7.2f}sn\n")
        with open("dogrulama.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue())

    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
