"""Kararlarin cevaba katilmasi.

Kararlar mevzuattan AYRI bir blokta veriliyor. Tek blokta birlestirilirse
model karardaki bir ifadeyi kanun hukmu gibi gosterebiliyor; ayrica kararlar
maddeleri baglamdan itip cevabin dayanagini zayiflatiyor.
"""
import config
from core.generate import baglam_kur, karar_baglami

KARARLAR = [
    {"kisa_ad": "9. Hukuk Dairesi 2015/1 E. 2016/2 K.",
     "gerekce": "Kıdem süresine istirahat raporları eklenir."},
    {"kisa_ad": "7. Hukuk Dairesi 2013/3 E. 2013/4 K.",
     "gerekce": "Fiilen çalışmaya başlanan tarih esastır."},
]
MADDELER = [{"mevzuat_adi": "İŞ KANUNU", "madde_no": "53",
             "baslik": "Yıllık izin", "metin": "İşçilere yıllık izin verilir."}]


def test_karar_baglami_kisa_adi_iceriyor():
    b = karar_baglami(KARARLAR)
    assert "9. Hukuk Dairesi" in b and "7. Hukuk Dairesi" in b
    assert "istirahat raporları" in b


def test_karar_baglami_siniri_asmiyor():
    cok = [{"kisa_ad": f"Daire {i}", "gerekce": "x" * 900} for i in range(30)]
    assert len(karar_baglami(cok, max_karakter=4000)) <= 4200


def test_bos_karar_bos_baglam():
    assert karar_baglami([]) == ""


def test_karar_baglami_mevzuattan_ayri():
    # Iki blok birbirine karismamali: madde metni karar blogunda gecmemeli.
    assert "Yıllık izin" not in karar_baglami(KARARLAR)
    assert "istirahat raporları" not in baglam_kur(MADDELER)


def test_metin_alani_da_kabul_ediliyor():
    # Sunucu 'metin', ic yapi 'gerekce' kullaniyor; ikisi de calismali.
    assert "deneme" in karar_baglami([{"kisa_ad": "X", "metin": "deneme metni"}])


def test_bayrak_var():
    assert isinstance(config.KARARLARI_CEVABA_KAT, bool)
