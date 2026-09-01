"""Cekirdek sorgu sinyalinin uc olcum setinde etkisi.

Sinyal: sorgunun soru kaliplarindan arindirilmis hali ayri bir arama olarak
calistirilip RRF ile birlestiriliyor. Hedef, dogal cumlelerdeki kaybi
kapatmak -- ayni bilgiyi soran anahtar kelime hali cok daha iyi calisiyor.

Cekirdegin bos dondugu sorgularda (zaten anahtar kelime ise) ikinci arama
hic yapilmiyor, yani bu sorgularda sonuc degismemeli.
"""
from __future__ import annotations

import io
import logging

import config
from core.embedder import Embedder
from core.retrieve import Retriever, cekirdek_sorgu
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
            sum(1 / x for x in s if x) / n)


def main() -> None:
    setler = [("el", EL), ("yerel", YEREL[:YEREL_KAC]), ("gemini", GEMINI)]
    out = io.StringIO()

    # Kac sorguda cekirdek devreye giriyor?
    out.write("cekirdegin devreye girdigi sorgu orani:\n")
    for ad, sorular in setler:
        n = sum(1 for q, _, _ in sorular if cekirdek_sorgu(q))
        out.write(f"  {ad:<8} {n:>4}/{len(sorular)}  (%{100*n/len(sorular):.0f})\n")
    out.write("\n")

    store, emb = VektorDeposu(), Embedder()
    baslik = f"{'cekirdek':>9}"
    for ad, s in setler:
        baslik += f" | {ad}({len(s)}) ilk1  ilk5    MRR"
    out.write(baslik + "\n" + "-" * len(baslik) + "\n")

    for acik in (False, True):
        config.CEKIRDEK_SORGU = acik
        r = Retriever(store, emb)
        r.ara("isinma", limit=5)
        satir = f"{'ACIK' if acik else 'KAPALI':>9}"
        for _, sorular in setler:
            a = olc(r, sorular)
            satir += f" | {a[0]:>10}{a[1]:>6}{a[2]:>7.3f}"
        out.write(satir + "\n")
        with open("cekirdek_olcum.txt", "w", encoding="utf-8") as f:
            f.write(out.getvalue())

    store.close()
    print(out.getvalue())


if __name__ == "__main__":
    main()
