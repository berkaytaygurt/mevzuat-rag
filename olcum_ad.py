"""Kisi adi tespiti yedi ayri belge turunde ne yapiyor.

    .venv\\Scripts\\python olcum_ad.py --cikti ad_olcum.txt

NEDEN TEK BELGE YETMEZ

Ilk olcum tek bir sentetik dilekcede 3/3 verdi -- ama istem o belgeye
bakilarak yazilmisti. Tek belgede iyi sonuc, yontemin degil o belgenin
olcumu olabilir. Bu betik ayni soruyu yedi belge turu ve alti ayri isim
bicimi uzerinde soruyor (bkz. tests/olcum_ad_seti.py).

IKI SAYI BIRLIKTE OKUNUR

  recall   : gold isimlerin kaci bulundu.
             Kacirmanin bedeli MUVEKKIL VERISININ SIZMASI.
  gurultu  : isim olmayan kac sey listelendi.
             Fazlasi listeyi okunmaz yapar, avukat ozelligi birakir.

Yalnizca recall'a bakmak yaniltir: her buyuk harfli diziyi listeleyen
bir yontem %100 recall alir ve hicbir ise yaramaz.
"""
from __future__ import annotations

import argparse
import io
import logging
import sys
import time

sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)

from core.ad_bul import adlari_bul          # noqa: E402
from core.belge import isim_adaylari        # noqa: E402
from core.generate import Generator         # noqa: E402
from tests.olcum_ad_seti import BELGELER    # noqa: E402


def _esler(gold: str, bulunan: list[str]) -> bool:
    """Gold isim listede var mi -- kapsama iliskisi yeterli.

    Model unvani atabilir ya da "M. Cufadar" yerine "Cufadar" yazabilir;
    bunlar dogru tespittir, maskeleme yine calisir.
    """
    g = gold.casefold()
    return any(g in b.casefold() or b.casefold() in g for b in bulunan)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", default=None)
    args = ap.parse_args()

    uretici = Generator(provider="local")
    # Isitma olcum disinda kalsin, ilk belgenin suresi sismesin.
    uretici.kisa("isin", sistem="Tek kelime yaz.", max_token=4)

    out = io.StringIO()
    out.write("KISI ADI TESPITI -- %d belge turu\n" % len(BELGELER))
    out.write("=" * 78 + "\n")

    t_recall = t_gold = t_gurultu = t_fazla = 0
    toplam_sure = 0.0
    eski_recall = 0

    for etiket, metin, goldler, yasaklar in BELGELER:
        t = time.time()
        bulunan = adlari_bul(metin, uretici)
        sure = time.time() - t
        toplam_sure += sure

        vurus = [g for g in goldler if _esler(g, bulunan)]
        kacan = [g for g in goldler if g not in vurus]
        # Yasakli liste: kurum/yer adi listeye girmis mi
        kirli = [b for b in bulunan
                 if any(y.casefold() in b.casefold() or
                        b.casefold() in y.casefold() for y in yasaklar)]
        # Gold'da olmayan her sey fazlalik (yasakli olmasa da)
        fazla = [b for b in bulunan if not any(_esler(g, [b]) for g in goldler)]

        t_recall += len(vurus)
        t_gold += len(goldler)
        t_gurultu += len(kirli)
        t_fazla += len(fazla)

        # Eski yol (sabit sozluk) karsilastirma icin
        eski = isim_adaylari(metin)
        eski_recall += sum(1 for g in goldler if _esler(g, eski))

        out.write("\n%-34s %5.1f sn\n" % (etiket, sure))
        out.write("   recall   : %d/%d\n" % (len(vurus), len(goldler)))
        if kacan:
            out.write("   KACIRDI  : %s\n" % ", ".join(kacan))
        if kirli:
            out.write("   GURULTU  : %s  <- kurum/yer, listelenmemeliydi\n"
                      % ", ".join(kirli))
        if fazla and not kirli:
            out.write("   fazladan : %s\n" % ", ".join(fazla))
        out.write("   bulunan  : %s\n" % (", ".join(bulunan) or "hicbiri"))

    n = len(BELGELER)
    out.write("\n" + "=" * 78 + "\nSONUC\n" + "=" * 78 + "\n")
    out.write("belge sayisi        : %d\n" % n)
    out.write("gold isim           : %d\n" % t_gold)
    out.write("recall (yerel model): %d/%d  (%%%.0f)\n"
              % (t_recall, t_gold, 100 * t_recall / max(t_gold, 1)))
    out.write("recall (sabit sozluk): %d/%d  (%%%.0f)\n"
              % (eski_recall, t_gold, 100 * eski_recall / max(t_gold, 1)))
    out.write("gurultu (kurum/yer) : %d\n" % t_gurultu)
    out.write("gold disi toplam    : %d\n" % t_fazla)
    out.write("sure                : %.1f sn (%.1f sn/belge)\n"
              % (toplam_sure, toplam_sure / n))

    metin = out.getvalue()
    # Once diske: konsol kodlamasi coktugunde olcum kaybolmasin.
    if args.cikti:
        with open(args.cikti, "w", encoding="utf-8") as f:
            f.write(metin)
    try:
        print(metin)
    except UnicodeEncodeError:
        kodlama = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.buffer.write(metin.encode(kodlama, errors="replace"))


if __name__ == "__main__":
    main()
