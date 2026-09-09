"""Maskeleme: dogru olani gizle, hukuk metnini bozma.

En onemli testler "maskeledi mi" degil, YANLIS MASKELEMEDI MI olanlar.
Fazla maskeleme sessizce analizi bozar: "4857" maskelenirse sistem
kanunu bulamaz ve kimse sebebini anlamaz.
"""
from __future__ import annotations

from core.maskele import Maske, iban_gecerli, tc_gecerli

# Saglamasi tutan ornek TC kimlik numarasi (gercek kisiye ait degil,
# algoritmayla uretildi).
GECERLI_TC = "10000000146"


def test_tc_saglamasi():
    assert tc_gecerli(GECERLI_TC)
    # Son hane bozulunca gecersiz
    assert not tc_gecerli("10000000147")
    assert not tc_gecerli("12345678901")
    assert not tc_gecerli("00000000000")   # sifirla baslayamaz
    assert not tc_gecerli("1234567890")    # 10 hane


def test_iban_saglamasi():
    assert iban_gecerli("TR33 0006 1005 1978 6457 8413 26")
    assert not iban_gecerli("TR33 0006 1005 1978 6457 8413 27")
    assert not iban_gecerli("TR12 3456")


def test_tc_ve_iban_maskeleniyor():
    m = Maske()
    metin = f"Müvekkil {GECERLI_TC} TC kimlik numaralı kişidir. " \
            "Hesap: TR33 0006 1005 1978 6457 8413 26"
    c = m.maskele(metin)
    assert GECERLI_TC not in c
    assert "6457 8413 26" not in c
    assert "[TCKN_1]" in c and "[IBAN_1]" in c


def test_onbir_haneli_her_sayi_maskelenmiyor():
    """Saglamasi tutmayan 11 hane TC degildir; dokunulmamali.

    Dosya numarasi, tutar, tarih dizisi de 11 hane olabilir. Desene
    bakip hepsini maskelemek metni gereksiz yere delik desik ederdi.
    """
    m = Maske()
    metin = "Dosya numarasi 12345678901 olarak kaydedilmistir."
    assert m.maskele(metin) == metin


def test_kanun_ve_madde_numaralari_korunuyor():
    """EN KRITIK TEST. 4857 maskelenirse sistem kanunu bulamaz."""
    m = Maske()
    metin = ("4857 sayılı İş Kanunu m.19 uyarınca, Yargıtay 9. Hukuk "
             "Dairesi 2019/1234 E. 2021/567 K. sayılı kararı gereğince "
             "6098 sayılı Türk Borçlar Kanunu m.315 uygulanır.")
    c = m.maskele(metin)
    assert c == metin, "hukuk metnindeki sayilar maskelenmemeli"


def test_eposta_ve_telefon():
    m = Maske()
    c = m.maskele("İletişim: ahmet.yilmaz@example.com, 0532 111 22 33")
    assert "example.com" not in c and "111 22 33" not in c
    assert "[EPOSTA_1]" in c and "[TEL_1]" in c


def test_ayni_deger_ayni_yer_tutucu():
    """Bir kisi belgede 40 kez gecse de tek yer tutucu almali.

    Farkli numara verilirse model tek kisiyi birden fazla taraf sanar
    ve tarafları karistirir -- sessiz ve tehlikeli bir hata.
    """
    m = Maske()
    c = m.maskele(f"{GECERLI_TC} ... daha sonra yine {GECERLI_TC} ...")
    assert c.count("[TCKN_1]") == 2
    assert len(m.tablo) == 1


def test_geri_koyma_metni_aynen_dondurur():
    m = Maske()
    asil = (f"Müvekkil {GECERLI_TC}, telefon 0532 111 22 33, "
            "e-posta ahmet@example.com")
    maskeli = m.maskele(asil)
    assert m.geri_koy(maskeli) == asil


def test_elle_eklenen_isim():
    """Isim tespiti makineye birakilamiyor; avukat isaretliyor."""
    m = Maske()
    m.ekle("Ahmet Yılmaz", "KISI")
    c = m.maskele_degerler("Davacı Ahmet Yılmaz, davalı şirkete karşı...")
    assert "Ahmet Yılmaz" not in c
    assert "[KISI_1]" in c
    assert m.geri_koy(c) == "Davacı Ahmet Yılmaz, davalı şirkete karşı..."


def test_ozet_sayiyor():
    m = Maske()
    m.maskele(f"{GECERLI_TC} ve ahmet@example.com ve 0532 111 22 33")
    o = m.ozet()
    assert o == {"TCKN": 1, "EPOSTA": 1, "TEL": 1}


def test_tablo_diske_yazilmiyor():
    """Esleme yalnizca bellekte. Nesne yok olunca esleme de yok olur."""
    m = Maske()
    m.maskele(GECERLI_TC)
    assert m.tablo                      # bellekte var
    assert not hasattr(m, "dosya")      # kalici bir yol tutmuyor
