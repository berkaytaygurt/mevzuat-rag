"""Devam olcum setinin bicimini korur.

Set elle yaziliyor; bozuk bir kayit sessizce yanlis bir olcum uretir.
Olculen seyin kendisinden once olcegin saglam olmasi gerekiyor.
"""
from __future__ import annotations

from tests.olcum_devam_seti import DEVAM, KONU_DEGISIMI, SORULAR


def test_kayit_bicimi():
    for k in SORULAR:
        assert len(k) == 6, k
        onceki, kisa, tam, kanun, madde, devam = k
        assert onceki and kisa and tam
        assert kanun.isdigit(), kanun
        assert madde is None or madde
        assert isinstance(devam, bool)


def test_a_setinde_kisa_soru_tamdan_farkli():
    """A setinin butun anlami kisa sorunun EKSIK olmasi.

    Once "kisa soru daha az harf icermeli" diye yazildi ve set dogru
    oldugu halde kaldi: "peki zina icin ayri bir sebep var mi" (36),
    "zina nedeniyle bosanma davasi"ndan (29) uzun. Aranan sey kisalik
    degil, sorunun kendi basina ayakta duramamasi -- ve bunu harf
    sayisi olcemez. Isaret eden bir yapi tasimasini ariyoruz.
    """
    isaretler = ("peki ", "buna", "bunda", "bu ", "istisna", "sınırı",
                 "manevi tazminat da", "eksik olursa", "açma süresi",
                 "nitelikli hâlleri", "reddetme süresi", "yılda en fazla",
                 "kamu görevlisine", "yazılmamış sayılırsa", "beş yıldan")
    for _onceki, kisa, tam, *_ in DEVAM:
        assert kisa != tam, kisa
        assert any(i in kisa.lower() for i in isaretler), kisa


def test_b_setinde_kisa_ile_tam_ayni():
    """B setinde soru zaten kendi basina anlamli: kisaltma yok.

    Olcum tavani ile baglamsiz kosulu ayni soru olmali ki, baglam
    eklendikten sonraki DUSUS gorulebilsin.
    """
    for _onceki, kisa, tam, *_ in KONU_DEGISIMI:
        assert kisa == tam, kisa


def test_b_setinde_konu_gercekten_degisiyor():
    """Onceki soru ile yeni soru ayni kanundan olmamali."""
    kanunlar = {
        "kira": "6098", "işveren": "4857", "yıllık": "4857",
        "hırsızlık": "5237", "hakaret": "5237", "evlenme": "4721",
        "boşanma": "4721", "kişisel": "6698", "ihtiyati": "6100",
        "haksız": "6098", "fazla": "4857",
    }
    for onceki, _kisa, _tam, kanun, _madde, devam in KONU_DEGISIMI:
        assert devam is False
        for anahtar, onceki_kanun in kanunlar.items():
            if anahtar in onceki.lower():
                assert onceki_kanun != kanun, onceki
                break


def test_devam_bayraklari_tutarli():
    assert all(k[5] for k in DEVAM)
    assert not any(k[5] for k in KONU_DEGISIMI)
    assert len(SORULAR) == len(DEVAM) + len(KONU_DEGISIMI)
