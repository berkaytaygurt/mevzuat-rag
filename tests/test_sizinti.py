"""Maskelemeden sonra kalan izlerin taranmasi.

Bu modulun isi YAKALAMAK degil ISARETLEMEK. O yuzden testler
"kacirmadi mi" diye bakiyor; fazla isaretlemek kabul edilir, cunku
yanlis alarmin bedeli iki saniye, kacirmanin bedeli muvekkil verisi.
"""
from __future__ import annotations

from core.sizinti import _korunani_ayikla, tara

METIN = """ANKARA 3. TÜKETİCİ MAHKEMESİNE
Dosya No: 2024/456 E.
DAVACI : [KISI_1] (T.C. [TCKN_1])
DAVALI : [KURUM_1]
Müvekkil, Jogger ticari adlı aracı [KURUM_2] bayisinden almıştır.
Şasi no VF1RJA00X12345678, vergi no 1234567890 olarak kayıtlıdır.
Müvekkil Beypazarı ilçesinde ikamet etmektedir.
Tanık Zübeyde Karaoğlan olayı görmüştür.
Tanık Zübeyde Karaoğlan beyanı alınmalıdır.
4857 sayılı İş Kanunu m.19 uyarınca işlem yapılmalıdır."""


def test_dosya_numarasi_yakalaniyor():
    """Esas numarasi bir davayi UYAP'ta tek basina bulmaya yetiyor."""
    kesin = [x["deger"] for x in tara(METIN)["kesin"]]
    assert any("2024/456" in k for k in kesin)


def test_sasi_ve_vergi_no_yakalaniyor():
    kesin = " ".join(x["deger"] for x in tara(METIN)["kesin"])
    assert "VF1RJA00X12345678" in kesin
    assert "1234567890" in kesin


def test_korunan_kelime_ismi_birlikte_gotermiyor():
    """EN ONEMLI TEST.

    Ilk surumde desen "Tanık Zübeyde Karaoğlan"i tek dizi olarak
    esliyor, "tanık" korunan kelime oldugu icin BUTUN diziyi -- ismi de
    -- atiyordu. Yani tam yakalamasi gereken seyi kaciriyordu.
    """
    olasi = [x["deger"] for x in tara(METIN)["olasi"]]
    assert "Zübeyde Karaoğlan" in olasi
    assert "Beypazarı" in olasi


def test_korunani_ayikla():
    assert _korunani_ayikla("Tanık Zübeyde Karaoğlan") == ["Zübeyde Karaoğlan"]
    assert _korunani_ayikla("Müvekkil Beypazarı") == ["Beypazarı"]
    assert _korunani_ayikla("Türk Borçlar Kanunu") == []


def test_cok_gecen_once_listeleniyor():
    """Belgede tekrar eden bir ad, tek gecen kelimeden daha olasi."""
    olasi = tara(METIN)["olasi"]
    assert olasi[0]["deger"] == "Zübeyde Karaoğlan"
    assert olasi[0]["gecis"] == 2


def test_hukuk_kelimeleri_isaretlenmiyor():
    """Fazla gurultu guveni bitirir: liste okunmaz hale gelir."""
    olasi = [x["deger"] for x in tara(METIN)["olasi"]]
    for yasak in ("İş Kanunu", "Kanunu", "Mahkemesine", "Tanık", "Müvekkil"):
        assert yasak not in olasi


def test_yer_tutucular_isaretlenmiyor():
    """[KISI_1] zaten maskelenmis; tekrar isaretlemek gurultu."""
    hepsi = " ".join(x["deger"] for x in
                     tara(METIN)["olasi"] + tara(METIN)["kesin"])
    assert "KISI_1" not in hepsi
    assert "TCKN_1" not in hepsi


def test_ruhsat_tek_basina_isaretlenmiyor():
    """Ilk surum rakam istemiyordu ve "ruhsatında" kelimesini
    isaretliyordu -- saf gurultu."""
    kesin = [x["deger"] for x in tara("Aracın ruhsatında yazdığı üzere")["kesin"]]
    assert not kesin


def test_bos_metin_cokmuyor():
    r = tara("")
    assert r["ozet"] == {"kesin": 0, "olasi": 0}
