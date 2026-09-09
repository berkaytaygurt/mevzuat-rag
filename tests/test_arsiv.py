"""Arsiv parcalama ve alinti secimi.

Buradaki testlerin cogu OLCULMUS bir hatayi kilitliyor. Ucu de sessiz
hatalardi: sistem calisiyor gorunuyordu, sonuclar sadece daha kotuydu.
"""
from __future__ import annotations

from core.arsiv import (KISA_AMA_DEGERLI, alinti_sec, bolumlere_ayir,
                        parcala, sorguyu_sadelestir)

DILEKCE = """ANKARA 5. İŞ MAHKEMESİ SAYIN HAKİMLİĞİNE

DAVACI : Ahmet Yılmaz (T.C. 10000000146)
ADRES : Kızılay Mah. Atatürk Bulvarı No:5/12 Çankaya/ANKARA

DAVALI : Örnek Yapı Sanayi ve Ticaret A.Ş.

KONU : İşçinin savunması alınmadan gerçekleştirilen feshin
geçersizliğinin tespiti ile işe iade istemidir.

AÇIKLAMALAR
1. Müvekkil davalı şirkette sekiz yıl çalışmıştır. Ücreti düzenli
ödenmiş, herhangi bir disiplin cezası almamıştır.
2. İşveren, 4857 sayılı İş Kanunu m.19'a aykırı biçimde müvekkilin
yazılı savunmasını almadan iş sözleşmesini feshetmiştir.

HUKUKİ SEBEPLER : 4857 sayılı İş Kanunu m.18, 19, 20.

DELİLLER : Hizmet dökümü, tanık beyanları ve her türlü yasal delil.

SONUÇ VE İSTEM : Yukarıda arz ve izah edilen nedenlerle davanın
kabulü ile müvekkilin işe iadesine karar verilmesini talep ederim."""


def test_ayni_satirdaki_baslik_taniniyor():
    """EN ONEMLI: gercek dilekce formati "KONU : icerik" seklinde.

    Ilk surum basligin kendi satirinda YALNIZ durmasini istiyordu.
    Sonucu iki katliydi: dilekcenin kendi ozeti (KONU) indekse hic
    girmedi, ve TARAF bolumleri ayiklanamadigi icin isim/TC/adres
    indekse sizdi. Ikisi de sessizdi.
    """
    basliklar = {b for b, _ in bolumlere_ayir(DILEKCE)}
    for beklenen in ("KONU", "DAVACI", "DAVALI", "AÇIKLAMALAR",
                     "HUKUKİ SEBEPLER", "DELİLLER", "SONUÇ VE İSTEM"):
        assert beklenen in basliklar, f"bulunamadi: {beklenen}"


def test_taraf_bilgisi_indekse_girmiyor():
    """Isim/TC/adres "hangi konuda yazmistim" sorusunun cevabi degil."""
    tam = " ".join(p["metin"] for p in parcala(DILEKCE, "x.txt"))
    for gizli in ("10000000146", "Kızılay Mah.", "Atatürk Bulvarı"):
        assert gizli not in tam, f"indekse sizdi: {gizli}"


def test_kalip_bolumler_indekse_girmiyor():
    """Her dilekcede ayni cumleler; indekslenirse hepsi benzesir."""
    bolumler = {p["bolum"] for p in parcala(DILEKCE, "x.txt")}
    assert "SONUÇ VE İSTEM" not in bolumler
    assert "DELİLLER" not in bolumler


def test_konu_ve_hukuki_sebepler_kisa_olsa_da_giriyor():
    """Ikisi de kisa ama en bilgilendirici bolumler."""
    bolumler = {p["bolum"] for p in parcala(DILEKCE, "x.txt")}
    assert "KONU" in bolumler
    assert "HUKUKİ SEBEPLER" in bolumler
    assert "HUKUKİ SEBEPLER" in KISA_AMA_DEGERLI


def test_konu_one_cikarilmiyor():
    """OLCULDU: KONU'yu agirliklandirmak ZARAR verdi.

    1.6 agirlikta MRR 0.791 -> 0.603, 1.15'te 0.674. Sebep: RRF
    puanlari cok kucuk ve carpan, 40. siradaki zayif bir KONU
    eslesmesini 5. siradaki guclu bir eslesmenin ustune cikariyor.
    Indekse ALMAK kazandiriyor, one CIKARMAK degil.
    """
    for p in parcala(DILEKCE, "x.txt"):
        assert p.get("agirlik", 1.0) == 1.0, p["bolum"]


def test_alinti_eslesen_yerden_geliyor():
    """Alintinin tek isi dosyayi TANITMAK.

    Once parcanin ilk 420 karakteri veriliyordu; eslesme bolumun
    sonundaysa ekranda olayin girisi cikiyor, aranan cumle
    gorunmuyordu -- alinti isesiz kaliyordu.
    """
    uzun = ("Giris cumlesi. " * 40) + "savunmasi alinmadan feshedilmistir. " \
           + ("Bitis cumlesi. " * 40)
    alinti = alinti_sec(uzun, "savunması alınmadan fesih")
    assert "savunmasi alinmadan" in alinti
    assert alinti.startswith("… ")


def test_alinti_kisa_metni_bozmuyor():
    kisa = "Kisa bir parca."
    assert alinti_sec(kisa, "herhangi bir sorgu") == kisa


def test_sorgu_sadelestirme_dolguyu_atiyor():
    sade = sorguyu_sadelestir("hani bir dosya vardı kiracı kira ödemiyordu o dilekçe")
    for dolgu in ("hani", "dosya", "dilekçe", "vardı"):
        assert dolgu not in sade.lower()
    assert "kiracı" in sade and "kira" in sade


def test_sadelestirme_her_seyi_atarsa_asil_sorgu_kaliyor():
    """Icerik atmaktansa sorguyu aynen birakmak yeglenir."""
    soru = "hani o dosya vardı"
    assert sorguyu_sadelestir(soru) == soru


def test_bicimi_taninmayan_belge_de_parcalaniyor():
    """Bilirkisi raporu, e-posta gibi belgeler de calismali."""
    duz = "Bu belgede hicbir dilekce basligi yok. " * 8
    assert parcala(duz, "y.txt"), "basliksiz belge parcalanamadi"
