"""Ayni hukuki meseleyi farkli bicimlerde sorup siralamayi karsilastirir.

Amac: kullaniciya "nasil yazarsan bulur" sorusunun olçulmus cevabini vermek.
"""
import logging, sys, time
sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)
import config
from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu

TESTLER = [
    ("savunma alinmadan fesih", "4857", "19", {
        "olay":   "musterim 4 yil 11 ay calisti, isveren devamsizlik nedeniyle savunmasini almadan sozlesmesini feshetti, bu fesih gecerli midir acaba",
        "soru":   "iscinin savunmasi alinmadan is sozlesmesi feshedilebilir mi",
        "kavram": "fesihte iscinin savunmasinin alinmasi",
        "ascii":  "fesihte iscinin savunmasinin alinmasi",
    }),
    ("yillik izin suresi", "4857", "53", {
        "olay":   "6 yildir ayni isyerinde calisan bir iscim var, kac gun yillik izin hakki oluyor merak ediyorum",
        "soru":   "yillik ucretli izin suresi kac gundur",
        "kavram": "yıllık ücretli izin süresi",
        "ascii":  "yillik ucretli izin suresi",
    }),
    ("kira bedelinin belirlenmesi", "6098", "344", {
        "olay":   "kiraci ile 2 yil once sozlesme yaptik, simdi kirayi enflasyon oraninda artirmak istiyorum ama kabul etmiyor ne yapabilirim",
        "soru":   "kira bedeli nasil belirlenir",
        "kavram": "kira bedelinin belirlenmesi",
        "ascii":  "kira bedelinin belirlenmesi",
    }),
    ("evlilik birliginin sarsilmasi", "4721", "166", {
        "olay":   "musterim esiyle 3 yildir ayni evde oturmuyor, siddetli gecimsizlik var, bosanma davasi acmak istiyor dayanak nedir",
        "soru":   "siddetli gecimsizlik nedeniyle bosanma",
        "kavram": "evlilik birliğinin temelinden sarsılması",
        "ascii":  "evlilik birliginin temelinden sarsilmasi",
    }),
    ("hakaret sucu", "5237", "125", {
        "olay":   "muvekkilime sosyal medyada kufur edildi ve asagilayici sozler soylendi, sikayet edersek ne olur",
        "soru":   "hakaret sucunun cezasi nedir",
        "kavram": "hakaret suçu",
        "ascii":  "hakaret sucu",
    }),
]

BICIMLER = ["olay", "soru", "kavram", "ascii"]


def sira(sonuc, kanun, madde):
    for i, m in enumerate(sonuc, 1):
        if m.get("mevzuat_no") == kanun and str(m.get("madde_no")) == madde:
            return i
    return None


def main():
    r = Retriever(VektorDeposu(), Embedder())
    config.SORGU_GENISLET = False
    r.ara("isinma", limit=3)               # model isinsin

    for mesele_ayir in (False, True):
        config.MESELE_AYIR = mesele_ayir
        etiket = "MESELE AYIRMA ACIK " if mesele_ayir else "MESELE AYIRMA KAPALI"
        toplam = {b: [] for b in BICIMLER}
        print(f"SONUC ===== {etiket}", flush=True)
        for konu, kanun, madde, bicimler in TESTLER:
            satir = []
            for b in BICIMLER:
                bas = time.time()
                y = sira(r.ara(bicimler[b], limit=10), kanun, madde)
                toplam[b].append(y)
                satir.append(f"{b}={y if y else '-'}({time.time()-bas:.1f}s)")
            print(f"SONUC {konu:<32} {kanun} m.{madde:<5} " + "  ".join(satir),
                  flush=True)
        for b in BICIMLER:
            v = toplam[b]
            mrr = sum(1 / x for x in v if x) / len(v)
            print(f"SONUC   {b:<7} ilk-1 {sum(1 for x in v if x==1)}/5 | "
                  f"ilk-5 {sum(1 for x in v if x and x<=5)}/5 | MRR {mrr:.3f}",
                  flush=True)
        if not mesele_ayir:
            print("SONUC", flush=True)


main()
