"""Sorgudan soru kaliplarinin atilmasi.

Olculen sorun: kidem tazminatinin sartlarini duzenleyen madde,

    "kidem tazminati sartlari"                         ->  1. sira
    "kidem tazminatina hak kazanmak icin ne kadar
     calismak gerekir"                                 -> 21. sira

Ayni bilgi soruluyor; fark soru kelimeleri. Bu testler cekirdek cikarmanin
konu kelimelerini korudugunu ve sorguyu bozmadigini guvenceye alir.
"""
from core.retrieve import cekirdek_sorgu


def test_soru_kaliplari_atiliyor():
    c = cekirdek_sorgu("kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir")
    assert "ne kadar" not in c and "gerekir" not in c
    assert "kıdem" in c and "tazminatına" in c and "çalışmak" in c


def test_kelime_ici_ek_bozulmuyor():
    # "tazminatı" icinde "mı", "tazminat" icinde "mi" geciyor; kelime siniri
    # olmadan bu kelimeler parcalaniyordu.
    c = cekirdek_sorgu("kıdem tazminatı ne zaman ödenir")
    assert "tazminatı" in c, f"kelime bozuldu: {c!r}"


def test_soru_eki_ayri_yazilinca_atiliyor():
    c = cekirdek_sorgu("işten çıkarılırsam tazminat alabilir miyim")
    assert "miyim" not in c
    assert "tazminat" in c


def test_zaten_anahtar_kelime_ise_bos_doner():
    # Atilacak sey yoksa ikinci arama yapmanin anlami yok.
    assert cekirdek_sorgu("kıdem tazminatı şartları") == ""
    assert cekirdek_sorgu("evlenme yaşı") == ""


def test_asiri_kisalirsa_bos_doner():
    # Geriye anlamli bir konu kalmiyorsa cekirdek kullanilmamali.
    assert cekirdek_sorgu("ne kadar") == ""
    assert cekirdek_sorgu("nedir") == ""


def test_bos_girdi():
    assert cekirdek_sorgu("") == ""
    assert cekirdek_sorgu("   ") == ""
