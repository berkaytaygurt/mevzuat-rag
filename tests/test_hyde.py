"""HyDE: soruyu kanun diline cevirip oyle arama.

OLCULDU (34 soruluk set, uretim ayarlariyla):
    HyDE kapali  1. sirada 23/34 | ilk-5 27/34 | MRR 0,734 | 1,4 sn
    HyDE acik    1. sirada 32/34 | ilk-5 33/34 | MRR 0,959 | 3,9 sn
"""
from core.hyde import varsayimsal_hukum
from core.retrieve import Retriever


class SahteUretici:
    def __init__(self, cevap):
        self.cevap = cevap
        self.cagri = 0

    def _gemini(self, istem, sistem=None, model=None):
        self.cagri += 1
        return self.cevap


def test_hukmu_donduruyor():
    u = SahteUretici("İşveren, işçinin savunmasını almadan sözleşmeyi feshedemez.")
    assert "savunmasını almadan" in varsayimsal_hukum("soru", u)


def test_hukuki_olmayan_soruda_bos_donuyor():
    """Model 'YOK' diyebilmeli.

    Cikis yolu olmadan istem ona 'hukum yaz' diye emrediyor ve model her
    soruyu zorla kanun diline ceviriyordu: "kahve nasil demlenir" sorusuna
    "Isci, kahveyi kaynar su ile ... demlemekle yukumludur" diye bir hukum
    uyduruyordu.
    """
    assert varsayimsal_hukum("kahve nasıl demlenir", SahteUretici("YOK")) == ""


def test_cok_kisa_cevap_yok_sayiliyor():
    assert varsayimsal_hukum("soru", SahteUretici("olmaz")) == ""


def test_uzun_metin_kirpiliyor():
    """Uzun metin BM25'i yavaslatiyor ve isabeti dusuruyor.

    Olculdu: 550 karakterlik HyDE ile arama 10,7 sn ve MRR 0,819;
    154 karakterlik ile 3,8 sn ve MRR 0,956.
    """
    from core.hyde import EN_FAZLA_KARAKTER
    u = SahteUretici("hüküm " * 200)
    assert len(varsayimsal_hukum("soru", u)) <= EN_FAZLA_KARAKTER


def test_uretim_hatasi_aramayi_engellemiyor():
    class Patlayan:
        def _gemini(self, *a, **k):
            raise RuntimeError("kota doldu")

    assert varsayimsal_hukum("soru", Patlayan()) == ""


def test_atif_sorgusunda_hyde_devreye_girmez():
    """Madde atfinda soru zaten kesin bir adres; HyDE onu bozar."""
    for s in ("TBK 344", "4857 madde 19", "TMK 166", "İş Kanunu 19. madde"):
        assert Retriever._atif_sorgusu(s), s
    for s in ("yıllık ücretli izin süresi", "işçinin savunması alınmadan fesih"):
        assert not Retriever._atif_sorgusu(s), s
