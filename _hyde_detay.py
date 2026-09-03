"""HyDE'nin soru bazinda etkisi ve uyarlamali (yalnizca zayifta) hali.

Iki soru:
1. HyDE hangi sorulari BOZUYOR? Ortalama iyilesme, tek tek gerilemeleri
   gizleyebilir; avukat icin bir sorunun kaybi bir sorunun kazanci kadar
   onemli.
2. HyDE'yi yalnizca ilk arama ZAYIFSA calistirsak kazancin ne kadari
   kalir? Sorgu genisletmede ayni yaklasim sureyi ucuzlatmisti.
"""
import logging
import sys
import time

sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)

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

ISTEM = "Soru: {soru}\n\nBu sorunun cevabını içerecek kanun maddesi metnini yaz."


def sira(sonuc, kanun, madde):
    for i, m in enumerate(sonuc, 1):
        if m.get("mevzuat_no") == kanun and (madde is None
                                             or str(m.get("madde_no")) == madde):
            return i
    return None


def mrr(v):
    return sum(1 / x for x in v if x) / len(v)


def main():
    emb = Embedder()
    r = Retriever(VektorDeposu(), emb)
    g = Generator()
    config.MESELE_AYIR = False
    config.SORGU_GENISLET = False
    r.ara("isinma", limit=3)

    ham_s, hyde_s, uyar_s = [], [], []
    hyde_sayisi = 0
    t_ham = t_hyde = 0.0
    bozulan, duzelen = [], []

    for soru, kanun, madde in SORULAR:
        b = time.time()
        ham = sira(r.ara(soru, limit=10), kanun, madde)
        guven = r.son_vektor_puani
        t_ham += time.time() - b
        ham_s.append(ham)

        b = time.time()
        try:
            sahte = (g._gemini(ISTEM.format(soru=soru), sistem=SISTEM,
                               model=config.GEMINI_HIZLI_MODEL) or "").strip()
        except Exception:
            sahte = ""
        h = sira(r.ara(sahte, limit=10), kanun, madde) if sahte else None
        t_hyde += time.time() - b
        hyde_s.append(h)

        # Uyarlamali: yalnizca ilk arama zayifsa HyDE'ye guven
        if guven < config.GENISLET_YETER:
            uyar_s.append(h if h else ham)
            hyde_sayisi += 1
        else:
            uyar_s.append(ham)

        hp = h if h else 99
        mp = ham if ham else 99
        if hp > mp:
            bozulan.append((soru[:44], ham, h))
        elif hp < mp:
            duzelen.append((soru[:44], ham, h))

    n = len(SORULAR)
    print(f"SONUC ==== {n} soru")
    for ad, v in (("ham sorgu", ham_s), ("HyDE (hep)", hyde_s),
                  ("HyDE (uyarlamali)", uyar_s)):
        print(f"SONUC {ad:<20} 1.sirada {sum(1 for x in v if x == 1):>2}/{n} | "
              f"ilk-5 {sum(1 for x in v if x and x <= 5):>2}/{n} | "
              f"MRR {mrr(v):.3f}", flush=True)
    print(f"SONUC uyarlamali HyDE cagrisi: {hyde_sayisi}/{n} soruda")
    print(f"SONUC sure: ham {t_ham/n:.1f} sn/soru | HyDE eki {t_hyde/n:.1f} sn/soru")
    print(f"SONUC HyDE ile DUZELEN: {len(duzelen)} | BOZULAN: {len(bozulan)}")
    for s, a, h in bozulan:
        print(f"SONUC   BOZULDU {a} -> {h} | {s}")
    for s, a, h in duzelen[:6]:
        print(f"SONUC   duzeldi {a} -> {h} | {s}")


main()
