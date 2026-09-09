"""Devam sorularinda baglam kurmanin ne kadar kazandiracagini olcer.

    .venv\\Scripts\\python olcum_devam.py
    .venv\\Scripts\\python olcum_devam.py --hyde-kapali   # Gemini cagrisi yok

NE OLCUYOR

Iki kosul karsilastiriliyor:

  BAGLAMSIZ : kullanicinin gercekte yazdigi kisa soru, tek basina
              aranir. Bugunku davranis budur -- sunucu gecmisi hic
              gormuyor.
  TAVAN     : ayni sorunun kendi basina ayakta duran tam hali. Baglam
              kurma isinin HEDEFI budur: "kullanici bastan acik acik
              yazsaydi" ne bulunurdu.

Ikisi arasindaki fark, baglam kurmanin kazandirabilecegi EN FAZLA
seydir. Fark kucukse ozellik yazmaya degmez; buyukse degecegini
biliriz. Ozellik yazildiktan sonra ucuncu bir kosul (BAGLAMLI) eklenip
tavana ne kadar yaklastigi olculecek.

B seti (konu degisimi) ayri raporlanir. Orada tavan ile baglamsiz ayni
sorudur; B'nin isi baglam eklendikten SONRA bozulup bozulmadigini
gostermek. Simdilik referans degeri kaydediliyor.
"""
from __future__ import annotations

import argparse
import io
import logging
import time

import config
from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_devam_seti import DEVAM, KONU_DEGISIMI

logging.basicConfig(level=logging.ERROR)


def sira_bul(sonuclar: list[dict], kanun: str, madde: str | None) -> int | None:
    for i, m in enumerate(sonuclar, 1):
        if str(m.get("mevzuat_no")) != kanun:
            continue
        if madde is None or str(m.get("madde_no")) == madde:
            return i
    return None


def ozet(siralar: list[int | None]) -> dict:
    n = len(siralar) or 1
    return {
        "n": len(siralar),
        "ilk1": sum(1 for s in siralar if s == 1),
        "ilk3": sum(1 for s in siralar if s and s <= 3),
        "mrr": sum(1 / s for s in siralar if s) / n,
    }


def kume_olc(retriever, kume, limit: int, out) -> tuple[dict, dict]:
    bagsiz: list[int | None] = []
    tavan: list[int | None] = []
    out.write(f"{'kisa':>5} {'tam':>5}  {'soru (kullanicinin yazdigi)':<46} beklenen\n")
    out.write("-" * 92 + "\n")
    for _onceki, kisa, tam, kanun, madde, _devam in kume:
        a = sira_bul(retriever.ara(kisa, limit=limit), kanun, madde)
        b = sira_bul(retriever.ara(tam, limit=limit), kanun, madde)
        bagsiz.append(a)
        tavan.append(b)
        out.write(f"{(a or '-'):>5} {(b or '-'):>5}  {kisa[:46]:<46} "
                  f"{kanun} m.{madde or '-'}\n")
    return ozet(bagsiz), ozet(tavan)


def yaz(out, ad: str, o: dict) -> None:
    n = o["n"]
    out.write(f"  {ad:<12} ilk-1 {o['ilk1']:>2}/{n}  ilk-3 {o['ilk3']:>2}/{n}  "
              f"MRR {o['mrr']:.3f}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--hyde-kapali", action="store_true",
                    help="HyDE'yi kapat (Gemini cagrisi yapilmaz)")
    ap.add_argument("--cikti", default=None)
    args = ap.parse_args()

    if args.hyde_kapali:
        config.HYDE = False

    store = VektorDeposu()
    retriever = Retriever(store, Embedder())

    out = io.StringIO()
    out.write("DEVAM SORUSU OLCUMU\n")
    out.write(f"HyDE: {'kapali' if args.hyde_kapali else 'acik'} | "
              f"rerank: {retriever.rerank} | limit: {args.limit}\n")
    basla = time.time()

    out.write(f"\n{'=' * 92}\nA SETI -- devam sorulari\n{'=' * 92}\n")
    a_bagsiz, a_tavan = kume_olc(retriever, DEVAM, args.limit, out)

    out.write(f"\n{'=' * 92}\nB SETI -- konu degisimi (kontrol)\n{'=' * 92}\n")
    b_bagsiz, b_tavan = kume_olc(retriever, KONU_DEGISIMI, args.limit, out)

    store.close()

    out.write(f"\n{'=' * 92}\nSONUC\n{'=' * 92}\n")
    out.write("A seti (devam sorulari):\n")
    yaz(out, "baglamsiz", a_bagsiz)
    yaz(out, "tavan", a_tavan)
    fark = a_tavan["mrr"] - a_bagsiz["mrr"]
    out.write(f"  --> baglam kurmanin kazandirabilecegi EN FAZLA: {fark:+.3f} MRR\n")

    out.write("\nB seti (konu degisimi -- baglam SONRASI bozulmamali):\n")
    yaz(out, "referans", b_bagsiz)

    sure = time.time() - basla
    out.write(f"\nsure: {sure:.1f} sn\n")

    metin = out.getvalue()
    print(metin)
    if args.cikti:
        with open(args.cikti, "w", encoding="utf-8") as f:
            f.write(metin)


if __name__ == "__main__":
    main()
