"""HyDE (Hypothetical Document Embeddings) denemesi.

FIKIR
Soru ile cevabin dili farkli. Kullanici "isten cikarildim tazminat alir
miyim" diye soruyor; kanun "isveren, is sozlesmesini feshederken ..."
diye yaziyor. Soruyu dogrudan gommek, iki farkli dil arasinda benzerlik
aramak demek.

HyDE, once modelden SORUYU CEVAPLAYAN varsayimsal bir metin yazmasini
istiyor, sonra o metni gomuyor. Yani soruyu cevabin diline cevirip
arama yapiyor.

BIZDE ZATEN SORGU GENISLETME VAR ama o farkli: mevcut sorguya hukuk
terimleri EKLIYOR. HyDE ise sorguyu bir kanun maddesi taklidiyle
DEGISTIRIYOR.

Bu betik ucunu de ayni sette olcuyor: ham sorgu, HyDE, ikisinin
karisimi (vektor ortalamasi).
"""
import logging
import sys
import time

sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)

import numpy as np

import config
from core.embedder import Embedder
from core.generate import Generator
from core.retrieve import Retriever
from core.vektor import VektorDeposu
from tests.olcum_seti import SORULAR

SISTEM = """Sen bir Türk hukuku uzmanısın. Sana bir soru verilir.
Sen o sorunun cevabını içerebilecek bir KANUN MADDESİ metni yazarsın.

Kurallar:
1. Gerçek madde numarası ya da kanun adı UYDURMA; yalnızca hüküm metni yaz.
2. Kanun dilini kullan: "...zorundadır", "...feshedilemez", "...hakkı vardır".
3. En fazla 4 cümle.
4. Açıklama yapma, yalnızca hüküm metnini yaz."""

ISTEM = """Soru: {soru}

Bu sorunun cevabını içerecek kanun maddesi metnini yaz."""


def sira(sonuc, kanun, madde):
    for i, m in enumerate(sonuc, 1):
        if m.get("mevzuat_no") == kanun and (madde is None
                                             or str(m.get("madde_no")) == madde):
            return i
    return None


def ozet(v, ad, sure):
    n = len(v)
    print(f"SONUC {ad:<22} 1. sirada {sum(1 for x in v if x == 1):>2}/{n} | "
          f"ilk-5 {sum(1 for x in v if x and x <= 5):>2}/{n} | "
          f"MRR {sum(1 / x for x in v if x) / n:.3f} | {sure:.1f} sn/soru", flush=True)


def main():
    emb = Embedder()
    store = VektorDeposu()
    r = Retriever(store, emb)
    g = Generator()
    config.MESELE_AYIR = False
    config.SORGU_GENISLET = False
    r.ara("isinma", limit=3)

    ham_s, hyde_s, karisim_s = [], [], []
    t_ham = t_hyde = 0.0
    for soru, kanun, madde in SORULAR:
        # 1) ham sorgu -- mevcut davranis
        b = time.time()
        ham_s.append(sira(r.ara(soru, limit=10), kanun, madde))
        t_ham += time.time() - b

        # 2) HyDE
        b = time.time()
        try:
            sahte = g._gemini(ISTEM.format(soru=soru), sistem=SISTEM,
                              model=config.GEMINI_HIZLI_MODEL) or ""
        except Exception as exc:
            print(f"SONUC HyDE uretilemedi: {str(exc)[:60]}", flush=True)
            sahte = ""
        if sahte.strip():
            hyde_s.append(sira(r.ara(sahte.strip(), limit=10), kanun, madde))
            # 3) karisim: iki vektorun ortalamasi, tek arama
            v1 = emb.encode_query(soru)
            v2 = emb.encode_query(sahte.strip())
            v = (v1 + v2) / 2
            v = v / (np.linalg.norm(v) or 1.0)
            karisim_s.append(sira(store.search(v, limit=10), kanun, madde))
        else:
            hyde_s.append(None)
            karisim_s.append(None)
        t_hyde += time.time() - b

    n = len(SORULAR)
    print(f"SONUC ==== HyDE denemesi ({n} soru)")
    ozet(ham_s, "ham sorgu", t_ham / n)
    ozet(hyde_s, "HyDE", t_hyde / n)
    ozet(karisim_s, "ham + HyDE karisim", t_hyde / n)


main()
