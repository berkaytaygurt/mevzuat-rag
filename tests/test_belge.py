"""Belge okuma ve aday tespiti.

Buradaki testlerin cogu SESSIZ SIZINTI testidir. Maskeleme yarim
kalirsa kimse fark etmez: metin maskelenmis gorunur, avukat guvenir,
veri yine de disari gider. Iki gercek hata bu sekilde bulundu ve
asagida kilitlendi.
"""
from __future__ import annotations

from core.belge import adaylar, adres_adaylari, isim_adaylari, kurum_adaylari, normalize
from core.maskele import Maske

DILEKCE = """DAVACI : Ahmet Yılmaz (T.C. 10000000146)
ADRES : Kızılay Mah. Atatürk Bulvarı No:5/12 Çankaya/ANKARA
VEKİLİ : Av. Ayşe Demir
 Cinnah Cad. No:41/7 Çankaya/ANKARA
DAVALI : Örnek Yapı Sanayi ve Ticaret A.Ş.
 Ostim OSB Mah. 1234. Sok. No:8 Yenimahalle/ANKARA
4857 sayılı İş Kanunu m.19 uyarınca savunma alınması zorunludur.
Yargıtay 9. Hukuk Dairesi 2019/1234 E. 2021/567 K."""


def test_kirilmaz_bosluk_normallesiyor():
    """PDF'ten cikan metinde bosluklar \\xa0 olarak geliyor.

    Duz replace ile eslesme yapan isim maskesi bu yuzden tutmuyordu.
    """
    assert normalize("Ahmet\xa0Yılmaz") == "Ahmet Yılmaz"
    assert normalize("fesih­") == "fesih"          # yumusak tire
    assert normalize("iki    bosluk") == "iki bosluk"


def test_satir_sonu_bolunmesi_birlesiyor():
    assert normalize("savun-\nma") == "savunma"


def test_isim_adaylari_kanun_adlarini_onermiyor():
    """EN KRITIK: kanun adi maskelenirse sistem kanunu bulamaz."""
    a = isim_adaylari(DILEKCE)
    assert "Ahmet Yılmaz" in a
    assert "Ayşe Demir" in a
    for yasak in ("İş Kanunu", "Hukuk Dairesi", "Türk Borçlar"):
        assert yasak not in a


def test_kurum_adi_TAMAMEN_yakalaniyor():
    """Kismi maskeleme hic maskelememekten kotudur.

    Ilk surumde regex her kelimenin buyuk harfle baslamasini istiyordu;
    kucuk harfli "ve" zinciri kesti ve yalnizca "Ticaret A.Ş." eslesti.
    Geriye "Örnek Yapı Sanayi ve" kaldi -- unvanin TANITICI kismi
    acikta, ustelik metin maskelenmis gorunuyordu.
    """
    k = kurum_adaylari(DILEKCE)
    assert "Örnek Yapı Sanayi ve Ticaret A.Ş." in k


def test_adres_adayi_satir_sonu_tasimiyor():
    """Aday satir sonu tasirsa metinde bulunamiyor ve maskelenmiyor.

    Aday tablosunda bosluklar tek bosluga indiriliyor; icinde satir
    sonu olan bir aday ham metinle eslesmiyordu ve adres sessizce
    disari gidiyordu.
    """
    for a in adres_adaylari(DILEKCE):
        assert "\n" not in a, a


def test_uctan_uca_sizinti_yok():
    """Butun adaylar maskelendiginde tanimlayici kalmamali."""
    ad = adaylar(DILEKCE)
    m = Maske()
    for tur, liste in ad.items():
        for x in liste:
            m.ekle(x, tur)
    maskeli = m.maskele_degerler(m.maskele(DILEKCE))
    for iz in ("Ahmet Yılmaz", "Ayşe Demir", "Örnek Yapı", "10000000146",
               "Kızılay", "Cinnah", "Ostim", "Yenimahalle"):
        assert iz not in maskeli, f"sizdi: {iz}"


def test_uctan_uca_hukuk_atiflari_korunuyor():
    """Bunlar bozulursa arama coker ve sebebi anlasilmaz."""
    ad = adaylar(DILEKCE)
    m = Maske()
    for tur, liste in ad.items():
        for x in liste:
            m.ekle(x, tur)
    maskeli = m.maskele_degerler(m.maskele(DILEKCE))
    for iz in ("4857", "m.19", "İş Kanunu", "9. Hukuk Dairesi",
               "2019/1234", "2021/567"):
        assert iz in maskeli, f"kayboldu: {iz}"


def test_bosluk_toleransli_eslesme():
    """PDF satir sonunda ismi bolebiliyor."""
    m = Maske()
    m.ekle("Ahmet Yılmaz", "KISI")
    assert "[KISI_1]" in m.maskele_degerler("Davacı Ahmet\nYılmaz beyan etti")
