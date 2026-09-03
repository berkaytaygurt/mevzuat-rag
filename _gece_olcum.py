"""Gece olcumu: duzeltilmis kulliyat uzerinde bekleyen her sey tek kosuda.

1. Olcum seti (34 soru)          -- kanunlarda %21 metin arttiktan sonra isabet
2. Madde atif bicimleri          -- "TBK 344", "4857 madde 19" hala 1. sirada mi
3. Mesele basligi istemi         -- sonuna alan etiketi yapisiyor mu, isabet
4. Vurgu maliyeti                -- vurgu acikken madde basina gercek sure
"""
import json
import logging
import re
import sys
import time

sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)

import config
from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu


def sira(sonuc, kanun, madde):
    for i, m in enumerate(sonuc, 1):
        if m.get("mevzuat_no") == kanun and (madde is None
                                             or str(m.get("madde_no")) == madde):
            return i
    return None


def yaz(s):
    print(f"SONUC {s}", flush=True)


def main():
    r = Retriever(VektorDeposu(), Embedder())
    config.MESELE_AYIR = False
    config.SORGU_GENISLET = False
    r.ara("isinma", limit=3)          # model isinsin

    # ---------- 1. olcum seti ----------
    from tests.olcum_seti import SORULAR
    yerler, bas = [], time.time()
    for soru, kanun, madde in SORULAR:
        yerler.append(sira(r.ara(soru, limit=10), kanun, madde))
    n = len(yerler)
    mrr = sum(1 / x for x in yerler if x) / n
    yaz(f"=== 1. OLCUM SETI ({n} soru)")
    yaz(f"ilk-1 {sum(1 for x in yerler if x == 1)}/{n} | "
        f"ilk-3 {sum(1 for x in yerler if x and x <= 3)}/{n} | "
        f"ilk-5 {sum(1 for x in yerler if x and x <= 5)}/{n} | "
        f"MRR {mrr:.3f} | {time.time() - bas:.0f} sn")
    yaz(f"siralar: {yerler}")

    # ---------- 2. atif bicimleri ----------
    yaz("=== 2. MADDE ATIF BICIMLERI")
    ATIFLAR = [("4857 madde 19", "4857", "19"), ("İş Kanunu 19. madde", "4857", "19"),
               ("TBK 344", "6098", "344"), ("2576 madde 3/A", "2576", "3/A"),
               ("TMK 166", "4721", "166"), ("TCK m.125", "5237", "125"),
               ("6098 sayılı kanun madde 344", "6098", "344"),
               ("türk medeni kanunu 166. madde", "4721", "166"),
               ("TMK 166 maddesi", "4721", "166")]
    ilk = 0
    for soru, kanun, madde in ATIFLAR:
        y = sira(r.ara(soru, limit=5), kanun, madde)
        ilk += 1 if y == 1 else 0
        if y != 1:
            yaz(f"  BASARISIZ: {soru} -> {y}")
    yaz(f"1. sirada: {ilk}/{len(ATIFLAR)}")

    # ---------- 3. mesele basligi ----------
    yaz("=== 3. MESELE BASLIGI")
    from core.generate import Generator
    from core.mesele import meseleleri_ayir
    g = Generator()
    ETIKET = re.compile(r"\b(iş|ceza|kira|aile|borçlar|medeni|idare|ticaret)\s+hukuku\s*$",
                        re.IGNORECASE)
    OLAYLAR = [
        ("müvekkilim 4 yıl 11 ay çalıştı, işveren devamsızlık nedeniyle "
         "savunmasını almadan sözleşmesini feshetti, geçerli midir", "4857", "19"),
        ("kiracım iki ay kirayı ödemedi, ihtar çektim ama cevap vermedi, "
         "tahliye edebilir miyim", "6098", "352"),
        ("müvekkilim eşiyle üç yıldır ayrı yaşıyor, şiddetli geçimsizlik var, "
         "boşanma davası açmak istiyor", "4721", "166"),
        ("işçi işe iade davasını kazandı ama işveren işe başlatmadı, "
         "ne kadar tazminat öder", "4857", "21"),
        ("komşum sosyal medyada müvekkilime küfür etti ve aşağıladı, "
         "şikayet edersek ne olur", "5237", "125"),
    ]
    etiketli, olay_s, baslik_s = 0, [], []
    for olay, kanun, madde in OLAYLAR:
        olay_s.append(sira(r.ara(olay, limit=10), kanun, madde))
        basliklar = meseleleri_ayir(olay, g)
        etiketli += sum(1 for b in basliklar if ETIKET.search(b))
        yerler2 = [sira(r.ara(b, limit=10), kanun, madde) for b in basliklar]
        baslik_s.append(min((y for y in yerler2 if y), default=None))
        yaz(f"  {kanun} m.{madde}: olay={olay_s[-1]} en_iyi_baslik={baslik_s[-1]}")
        for b in basliklar:
            yaz(f"    - {b}")
    for ad, v in (("olay anlatimi", olay_s), ("en iyi baslik", baslik_s)):
        yaz(f"{ad:<16} 1. sirada {sum(1 for x in v if x == 1)}/5 | "
            f"MRR {sum(1 / x for x in v if x) / len(v):.3f}")
    yaz(f"sonuna alan etiketi yapisan baslik: {etiketli}")

    # ---------- 4. vurgu maliyeti ----------
    yaz("=== 4. VURGU MALIYETI")
    from core.vurgu import parcalari_hazirla
    maddeler = r.ara("işçinin savunması alınmadan fesih", limit=10)
    parcalari_hazirla(maddeler[0]["metin"], "deneme", r.reranker)   # isit
    bas = time.time()
    isaretli = 0
    for m in maddeler:
        p = parcalari_hazirla(m["metin"], "işçinin savunması alınmadan fesih",
                              r.reranker)
        isaretli += sum(1 for x in p if x.get("vurgu"))
    gecen = time.time() - bas
    yaz(f"10 madde icin {gecen:.1f} sn (madde basina {gecen / 10:.2f} sn), "
        f"isaretlenen parca: {isaretli}")


main()
