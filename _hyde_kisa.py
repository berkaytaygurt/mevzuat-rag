"""Kisa HyDE: tek cumlelik varsayimsal hukum.

Uzun HyDE (4 cumle, 618 karakter) sorguyu 12,2 saniyeye cikariyordu ama
Gemini'nin payi yalnizca 2 saniye. Geri kalani BM25: 618 karakterlik
metin ~80 arama terimi demek ve BM25 275 bin belgeyi o kadar terimle
tariyor. Normal sorgu 4 terim.
"""
import logging, sys, time
sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)
import config
from core.embedder import Embedder
from core.generate import Generator
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_seti import SORULAR

UZUN = """Sen bir Türk hukuku uzmanısın. Sana bir soru verilir.
Sen o sorunun cevabını içerebilecek bir KANUN MADDESİ metni yazarsın.
Gerçek madde numarası ya da kanun adı UYDURMA; yalnızca hüküm metni yaz.
Kanun dilini kullan. En fazla 4 cümle. Açıklama yapma."""
KISA = """Sen bir Türk hukuku uzmanısın. Soruyu cevaplayan kanun maddesi
hükmünü yaz. Madde numarası ya da kanun adı uydurma. TEK CÜMLE, en fazla
25 kelime. Kanun dilini kullan. Açıklama yapma."""


def sira(s, kanun, madde):
    for i, m in enumerate(s, 1):
        if m.get("mevzuat_no") == kanun and (madde is None
                                             or str(m.get("madde_no")) == madde):
            return i
    return None


def main():
    r = Retriever(VektorDeposu(), Embedder())
    g = Generator()
    config.MESELE_AYIR = False
    config.SORGU_GENISLET = False
    r.ara("isinma", limit=3)

    for ad, sis in (("kisa HyDE", KISA), ("uzun HyDE", UZUN)):
        yerler, t_uret, t_ara, uzunluk = [], 0.0, 0.0, []
        for soru, kanun, madde in SORULAR:
            b = time.time()
            try:
                sahte = (g._gemini(f"Soru: {soru}\n\nKanun maddesi hükmünü yaz.",
                                   sistem=sis,
                                   model=config.GEMINI_HIZLI_MODEL) or "").strip()
            except Exception:
                sahte = ""
            t_uret += time.time() - b
            uzunluk.append(len(sahte))
            b = time.time()
            yerler.append(sira(r.ara(sahte, limit=10), kanun, madde) if sahte else None)
            t_ara += time.time() - b
        n = len(yerler)
        print(f"SONUC {ad:<11} 1.sirada {sum(1 for x in yerler if x==1):>2}/{n} | "
              f"ilk-5 {sum(1 for x in yerler if x and x<=5):>2}/{n} | "
              f"MRR {sum(1/x for x in yerler if x)/n:.3f} | "
              f"uretim {t_uret/n:.1f} sn + arama {t_ara/n:.1f} sn | "
              f"metin {sum(uzunluk)//n} karakter", flush=True)


main()
