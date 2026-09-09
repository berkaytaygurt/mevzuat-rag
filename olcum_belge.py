"""Mesele cikarimini YEREL model Gemini kadar iyi yapabiliyor mu?

    .venv\\Scripts\\python olcum_belge.py
    .venv\\Scripts\\python olcum_belge.py --yereli-atla   # yalnizca Gemini

NEDEN ONEMLI

Avukatin dilekcesi hassas. Mesele cikarimini yerel model yapabiliyorsa
belge bilgisayardan hic cikmaz; disariya yalnizca "iscinin savunmasi
alinmadan feshi" gibi kisisel veri tasimayan BASLIKLAR gider.
Yapamiyorsa dilekcenin tamami Google'a gitmek zorunda kalir.

UC KOSUL

  AYIRMA YOK : olay anlatimi oldugu gibi aranir (temel cizgi)
  GEMINI     : meseleler Gemini ile ayrilir, her biri ayri aranir
  YEREL      : meseleler yerel modelle ayrilir, geri kalani ayni

Arama tarafi UC kosulda da ayni; degisen tek sey meseleleri kimin
cikardigi.

OLCU

Her olayin birden fazla dogru maddesi var, o yuzden MRR tek basina
yetmiyor. Iki sayi birlikte okunmali:

  kapsama    : gold maddelerin kaci sonuclarda cikti
  gosterilen : kac ayri madde gosterildi

Ikincisi olmadan birincisi yaniltir: daha cok mesele cikaran model
daha cok arama yapar ve kapsamayi kendiliginden yukseltir. Avukatin
okumasi gereken madde sayisi da artar; bedava kazanc degil.
"""
from __future__ import annotations

import argparse
import io
import logging
import time

import config
from core.embedder import Embedder
from core.generate import Generator
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_belge_seti import OLAYLAR

logging.basicConfig(level=logging.ERROR)


class YerelUretici:
    """meseleleri_ayir() uretici._gemini() cagiriyor; yerele yonlendirir.

    Kodda su an saglayici GLOBAL: ya hepsi Gemini ya hepsi yerel. Cagri
    basina secim ozelligini olcumden ONCE yazmiyoruz -- olcum "gerekli
    mi" sorusunu cevaplayacak. Bu kabuk o yuzden gecici.
    """

    def __init__(self) -> None:
        self._g = Generator(provider="local")

    def _gemini(self, istem: str, sistem: str | None = None,
                model: str | None = None) -> str:
        return self._g._local(istem, sistem=sistem)


def birlesik_ara(retriever, meseleler: list[str], limit: int) -> dict:
    """Her meseleyi ayri arar, en iyi sirayi koruyarak birlestirir."""
    en_iyi: dict[tuple[str, str], int] = {}
    for m in meseleler:
        for sira, k in enumerate(retriever.ara(m, limit=limit), 1):
            anahtar = (str(k.get("mevzuat_no")), str(k.get("madde_no")))
            if anahtar not in en_iyi or sira < en_iyi[anahtar]:
                en_iyi[anahtar] = sira
    return en_iyi


def puanla(bulunanlar: dict, goldler: list[tuple[str, str]]) -> tuple[int, float]:
    vurus = 0
    mrr = 0.0
    for g in goldler:
        sira = bulunanlar.get(g)
        if sira:
            vurus += 1
            mrr += 1 / sira
    return vurus, mrr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--yereli-atla", action="store_true")
    ap.add_argument("--cikti", default=None)
    args = ap.parse_args()

    store = VektorDeposu()
    retriever = Retriever(store, Embedder())
    gemini = Generator(provider="gemini")
    yerel = None if args.yereli_atla else YerelUretici()

    from core.mesele import meseleleri_ayir

    out = io.StringIO()
    out.write("MESELE CIKARIMI: GEMINI vs YEREL MODEL\n")
    out.write(f"model: {config.LOCAL_MODEL_PATH} | GPU katmani: "
              f"{config.LOCAL_GPU_LAYERS} | limit: {args.limit}\n")

    toplam_gold = sum(len(g) for _, g in OLAYLAR)
    sayac = {ad: {"vurus": 0, "mrr": 0.0, "gosterilen": 0, "sure": 0.0,
                  "mesele": 0}
             for ad in ("ayirma yok", "gemini", "yerel")}

    for i, (olay, goldler) in enumerate(OLAYLAR, 1):
        out.write(f"\n{'=' * 92}\n{i}. {olay[:86]}...\n")
        out.write(f"   gold: {', '.join(k + ' m.' + m for k, m in goldler)}\n")

        # --- Kosul C: ayirma yok ---
        config.MESELE_AYIR = False
        t = time.time()
        ham = {}
        for sira, k in enumerate(retriever.ara(olay, limit=args.limit), 1):
            ham[(str(k.get("mevzuat_no")), str(k.get("madde_no")))] = sira
        sure = time.time() - t
        v, m = puanla(ham, goldler)
        sayac["ayirma yok"]["vurus"] += v
        sayac["ayirma yok"]["mrr"] += m
        sayac["ayirma yok"]["gosterilen"] += len(ham)
        sayac["ayirma yok"]["sure"] += sure
        out.write(f"   ayirma yok : {v}/{len(goldler)} gold, "
                  f"{len(ham)} madde, {sure:.1f} sn\n")
        config.MESELE_AYIR = True

        # --- Kosul A ve B ---
        for ad, uretici in (("gemini", gemini), ("yerel", yerel)):
            if uretici is None:
                continue
            t = time.time()
            try:
                meseleler = meseleleri_ayir(olay, uretici)
            except Exception as exc:
                out.write(f"   {ad:<11}: HATA {str(exc)[:60]}\n")
                continue
            if not meseleler:
                out.write(f"   {ad:<11}: mesele cikaramadi\n")
                continue
            bulunan = birlesik_ara(retriever, meseleler, args.limit)
            sure = time.time() - t
            v, m = puanla(bulunan, goldler)
            sayac[ad]["vurus"] += v
            sayac[ad]["mrr"] += m
            sayac[ad]["gosterilen"] += len(bulunan)
            sayac[ad]["sure"] += sure
            sayac[ad]["mesele"] += len(meseleler)
            out.write(f"   {ad:<11}: {v}/{len(goldler)} gold, "
                      f"{len(bulunan)} madde, {len(meseleler)} mesele, "
                      f"{sure:.1f} sn\n")
            for ms in meseleler:
                out.write(f"                  - {ms[:76]}\n")

    store.close()

    out.write(f"\n{'=' * 92}\nSONUC ({len(OLAYLAR)} olay, "
              f"{toplam_gold} gold madde)\n{'=' * 92}\n")
    out.write(f"{'kosul':<12} {'kapsama':>14} {'MRR':>7} "
              f"{'gosterilen':>11} {'mesele':>7} {'sure/olay':>10}\n")
    out.write("-" * 92 + "\n")
    for ad, s in sayac.items():
        if not s["gosterilen"]:
            continue
        n = len(OLAYLAR)
        out.write(f"{ad:<12} {s['vurus']:>5}/{toplam_gold} "
                  f"(%{100 * s['vurus'] / toplam_gold:>3.0f}) "
                  f"{s['mrr'] / toplam_gold:>7.3f} "
                  f"{s['gosterilen'] / n:>11.1f} "
                  f"{s['mesele'] / n:>7.1f} "
                  f"{s['sure'] / n:>9.1f} sn\n")

    metin = out.getvalue()
    print(metin)
    if args.cikti:
        with open(args.cikti, "w", encoding="utf-8") as f:
            f.write(metin)


if __name__ == "__main__":
    main()
