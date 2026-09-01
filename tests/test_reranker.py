"""Yeniden siralama katmani testleri (model yuklemez)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from core.reranker import Reranker  # noqa: E402
from core.retrieve import Retriever  # noqa: E402
from core.store import MevzuatStore  # noqa: E402


class SahteModel:
    """Belirli bir maddeye yuksek puan veren sahte cross-encoder."""

    def __init__(self, hedef_madde: str):
        self.hedef = hedef_madde
        self.cagrildi = False

    def predict(self, ciftler, **kw):
        self.cagrildi = True
        # RERANK_KATLA acikken metin ASCII'ye katlanip kucuk harfe dusuruluyor;
        # karsilastirmayi buyuk/kucuk harften bagimsiz yapiyoruz.
        return [1.0 if f"madde {self.hedef}" in belge.lower() else 0.1
                for _soru, belge in ciftler]


def _kayit(no: str, baslik: str = "") -> dict:
    return {"chunk_id": f"K-1-5-{no}", "mevzuat_no": "1", "madde_no": no,
            "mevzuat_adi": "TEST KANUNU", "baslik": baslik,
            "metin": f"{no} numarali maddenin metni", "skor": 0.01}


def test_madde_metni_baglam_icerir():
    """Madde govdesi tek basina konuyu anlatmayabiliyor; kanun adi ve
    baslik da cross-encoder'a verilmeli."""
    metin = Reranker._madde_metni(_kayit("53", "Yıllık ücretli izin"))
    assert "TEST KANUNU" in metin
    assert "Madde 53" in metin
    assert "Yıllık ücretli izin" in metin


def test_sirala_hedefi_one_alir():
    r = Reranker()
    r._model = SahteModel("141")
    adaylar = [_kayit("147"), _kayit("144"), _kayit("141"), _kayit("143")]
    sonuc = r.sirala("hırsızlık cezası", adaylar, limit=3)
    assert sonuc[0]["madde_no"] == "141"
    assert len(sonuc) == 3
    assert sonuc[0]["yeniden_siralandi"] is True


def test_tek_aday_modeli_cagirmaz():
    r = Reranker()
    sahte = SahteModel("1")
    r._model = sahte
    assert r.sirala("soru", [_kayit("1")], limit=5)[0]["madde_no"] == "1"
    assert not sahte.cagrildi, "tek aday icin model calistirilmamali"


def test_bos_liste_cokmez():
    r = Reranker()
    r._model = SahteModel("1")
    assert r.sirala("soru", [], limit=5) == []


def test_varsayilan_ayarlar_makul():
    """Olculen denge: 25 aday / 256 token.

    Genisletmek ilk asamanin tavanini yukseltiyor (12 adayda %88, 50 adayda
    %97) ama ciktiyi degistirmiyor; 50 ile 25 ayni sonucu veriyor.
    """
    assert 20 <= config.RERANK_ADAY <= 60
    assert config.RERANK_MAX_SEQ <= 512


def test_harmanlama_agirligi_makul():
    """Saf cross-encoder (1.0) olculen en kotu ayar: ilk asamanin RRF puani
    madde numarasi eslesmesi gibi sinyalleri tasiyor ve atilmasi kayip."""
    assert 0.7 <= config.RERANK_AGIRLIK < 1.0


def test_retriever_rerank_bayragini_saygi_gosterir():
    r = Retriever.__new__(Retriever)
    r.rerank = False
    assert r.rerank is False


def test_katlama_aksan_farkini_kaldirir():
    """Aksanli ve ASCII sorgu, cross-encoder'a ayni sekilde ulasmali.

    Gozlenen hata: "evlenme yaşı kaç" sorgusunda TMK m.124 birinci sirada
    gelirken, ayni sorunun "evlenme yasi kac" yazimi m.129'u one cikariyordu.
    """
    if not config.RERANK_KATLA:
        return

    from core.retrieve import _tr_katla

    assert _tr_katla("hırsızlık suçunun cezası") == _tr_katla("hirsizlik sucunun cezasi")
    assert _tr_katla("evlenme yaşı kaç") == _tr_katla("evlenme yasi kac")


def test_olcekleme_farkli_olcekleri_esitler():
    """Cross-encoder puani ile RRF puani cok farkli olceklerde; olceklemeden
    toplamak buyuk olanin digerini ezmesi demek."""
    from core.reranker import _olcekle
    assert _olcekle([1.0, 2.0, 3.0]) == [0.0, 0.5, 1.0]
    assert _olcekle([0.001, 0.002, 0.003]) == [0.0, 0.5, 1.0]


def test_olcekleme_uc_durumlar():
    from core.reranker import _olcekle
    assert _olcekle([]) == []
    assert _olcekle([5.0, 5.0]) == [0.5, 0.5]      # hepsi ayni -> notr


def test_harmanlama_iki_sinyali_de_kullanir():
    """Agirlik 0.5 iken ilk asamada onde olan aday, cross-encoder esitse
    one gecmeli."""
    import config as cfg
    from core.reranker import Reranker

    eski = cfg.RERANK_AGIRLIK
    cfg.RERANK_AGIRLIK = 0.5
    try:
        r = Reranker()
        r._model = type("M", (), {"predict": lambda self, c, **k: [0.5] * len(c)})()
        adaylar = [{**_kayit("1"), "skor": 0.01}, {**_kayit("2"), "skor": 0.99}]
        assert r.sirala("soru", adaylar, limit=2)[0]["madde_no"] == "2"
    finally:
        cfg.RERANK_AGIRLIK = eski


# --------------------------------------------------------------------------
# Ek / Gecici madde cezasi
# --------------------------------------------------------------------------
@pytest.mark.parametrize("madde_no,ikincil", [
    ("53", False), ("141", False),
    ("Ek 3", True), ("Geçici 7", True), ("Mükerrer 5", True),
])
def test_ikincil_madde_tespiti(madde_no, ikincil):
    from core.reranker import _ikincil_madde
    assert _ikincil_madde({"madde_no": madde_no}) is ikincil


def test_ikincil_madde_geri_planda_kalir():
    """Gozlenen hata: "fazla calisma ucreti" sorgusu Is Kanunu m.41 yerine
    Vergi Usul Kanunu Ek 13'u one cikariyordu -- baslik birebir ayni ama
    madde ikincil. Esit puanda asil madde one gecmeli."""
    import config as cfg
    from core.reranker import Reranker

    eski = cfg.EK_MADDE_CEZASI
    cfg.EK_MADDE_CEZASI = 0.05
    try:
        r = Reranker()
        r._model = type("M", (), {"predict": lambda self, c, **k: [0.9] * len(c)})()
        adaylar = [
            {**_kayit("Ek 13"), "skor": 0.02},
            {**_kayit("41"), "skor": 0.02},
        ]
        assert r.sirala("fazla çalışma ücreti", adaylar, limit=2)[0]["madde_no"] == "41"
    finally:
        cfg.EK_MADDE_CEZASI = eski
