"""Cok olgulu sorularda mesele ayirmanin etkisini olcer."""
import logging
import sys

sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)

import config
from core.embedder import Embedder
from core.mesele import cok_olgulu_mu, meseleleri_ayir
from core.retrieve import Retriever
from core.vektor import VektorDeposu

# (soru, bulunmasi beklenen kanun_no, madde_no)
TESTLER = [
    ("isci 4 yil 11 ay calisti, isveren devamsizlik nedeniyle savunma "
     "almadan feshetti, fesih gecerli mi", "4857", "19"),
    ("kiraci iki ay kira odemedi, ihtar cektim, tahliye davasi acabilir miyim",
     "6098", "315"),
    ("ise iade davasini kazandik ama isveren ise baslatmadi, tazminat nasil "
     "hesaplanir", "4857", "21"),
    ("isci istifa etti ama maasi odenmemisti, kidem tazminati alabilir mi",
     "4857", "24"),
]


def sira(sonuc, kanun, madde):
    for i, m in enumerate(sonuc, 1):
        if m.get("mevzuat_no") == kanun and str(m.get("madde_no")) == madde:
            return i
    return None


def main() -> None:
    store, emb = VektorDeposu(), Embedder()
    r = Retriever(store, emb)
    config.SORGU_GENISLET = True
    config.GENISLET_HEP = True
    r.ara("isinma", limit=3)

    for etiket, ayir in (("KAPALI", False), ("ACIK ", True)):
        config.MESELE_AYIR = ayir
        bulunan = 0
        for soru, kanun, madde in TESTLER:
            s = r.ara(soru, limit=10)
            y = sira(s, kanun, madde)
            bulunan += 1 if y else 0
            print(f"SONUC {etiket} | {kanun} m.{madde} sirasi: "
                  f"{y if y else 'YOK':<4} | {soru[:42]}")
        print(f"SONUC {etiket} | ilk 10'da bulunan: {bulunan}/{len(TESTLER)}")
        print("SONUC")

    # ornek ayirma
    config.MESELE_AYIR = True
    soru = TESTLER[0][0]
    print(f"SONUC cok olgulu mu: {cok_olgulu_mu(soru)}")
    print(f"SONUC meseleler: {meseleleri_ayir(soru, r.genisletici.uretici)}")


if __name__ == "__main__":
    main()
