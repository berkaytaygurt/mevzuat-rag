"""Cevap uretimi yardimcilarinin testleri (model yuklemez)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.generate import atiflari_dogrula, baglam_kur, temizle  # noqa: E402

MADDELER = [
    {"mevzuat_adi": "İŞ KANUNU", "madde_no": "53",
     "baslik": "Yıllık ücretli izin", "metin": "Ondört günden az olamaz.",
     "mulga": False},
    {"mevzuat_adi": "TÜRK MEDENİ KANUNU", "madde_no": "170",
     "baslik": "Boşanma", "metin": "Hâkim boşanmaya karar verir.", "mulga": False},
]


# --------------------------------------------------------------------------
# Bakim notlarinin temizlenmesi
# --------------------------------------------------------------------------
@pytest.mark.parametrize("girdi", [
    "Amaç (Ek cümle: 10/9/2014-6552/5 md.) budur.",
    "Madde 5 – (Ek: 6/2/2014-6518/57 md.) Ayrım yapılamaz.",
    "(Değişik fıkra: 23/7/2020-7252/5 md.) İşveren bildirir.",
    "(Mülga: 2/3/2024-7499/33 md.)",
])
def test_bakim_notu_temizlenir(girdi):
    """Model bu notlari cevaba kopyaliyordu; kullaniciya anlamsiz goruntu."""
    assert "md.)" not in temizle(girdi)


@pytest.mark.parametrize("girdi", [
    "İşçiye ondört gün izin verilir.",
    "Taraflar 1/1/2020 tarihinde sözleşme yapmıştır.",   # tarih var ama hukum
])
def test_gercek_hukum_silinmez(girdi):
    assert temizle(girdi) == girdi


# --------------------------------------------------------------------------
# Atif dogrulama
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cevap", [
    "İşçiye ondört gün izin verilir (İş Kanunu m.53).",
    "Hâkim karar verir (Türk Medeni Kanunu m.170).",
    "Kısaltma da geçerli (İş K. m.53).",
    "Hiç kaynak göstermeyen cümle.",
])
def test_gecerli_atif_supheli_isaretlenmez(cevap):
    assert atiflari_dogrula(cevap, MADDELER) == []


@pytest.mark.parametrize("cevap,beklenen", [
    ("Boşanma (İşçiye Mevzuati m.12) şunlardır.", "İşçiye Mevzuati m.12"),
    ("İzin (İş Kanunu m.99) belirlenir.", "İş Kanunu m.99"),
])
def test_uydurma_atif_yakalanir(cevap, beklenen):
    """Gozlenen hata: gercek kaynak TMK m.170 iken model
    '(Isciye Mevzuati m.12)' yazmisti. Kullanici bunu dayanak sanabilir."""
    assert atiflari_dogrula(cevap, MADDELER) == [beklenen]


# --------------------------------------------------------------------------
# Baglam kurma
# --------------------------------------------------------------------------
def test_baglam_madde_etiketi_icerir():
    b = baglam_kur(MADDELER)
    assert "İŞ KANUNU - Madde 53" in b
    assert "Yıllık ücretli izin" in b


def test_baglam_mulga_uyarisi_koyar():
    m = [{**MADDELER[0], "mulga": True}]
    assert "yürürlükten kalkmıştır" in baglam_kur(m)


def test_baglam_karakter_sinirina_uyar():
    cok = [{**MADDELER[0], "metin": "x" * 5000} for _ in range(10)]
    assert len(baglam_kur(cok, max_karakter=6000)) <= 6000


# --------------------------------------------------------------------------
# Sayi dogrulama
# --------------------------------------------------------------------------
BAGLAM = ("[İŞ KANUNU - Madde 53]\nİşçilere verilecek yıllık ücretli izin süresi, "
          "hizmet süresi; a) Bir yıldan beş yıla kadar olanlara ondört günden, "
          "b) Beş yıldan fazla onbeş yıldan az olanlara yirmi günden, "
          "c) Onbeş yıl ve daha fazla olanlara yirmialtı günden az olamaz.")


def test_yazili_sayilar_cozulur():
    from core.generate import _yazili_sayilar
    bulunan = _yazili_sayilar(BAGLAM)
    for beklenen in (14, 20, 26):
        assert beklenen in bulunan, f"{beklenen} cozulemedi"


@pytest.mark.parametrize("cevap", [
    "Ondört, yirmi ve yirmialtı gün olarak belirlenir.",
    "14, 20 ve 26 gün olarak belirlenir.",
    "Yıllık izin hakkından vazgeçilemez.",
])
def test_kaynaktaki_sayi_supheli_isaretlenmez(cevap):
    from core.generate import sayilari_dogrula
    assert sayilari_dogrula(cevap, BAGLAM) == []


@pytest.mark.parametrize("cevap,beklenen", [
    ("14 gün olmak üzere 24 gün arasında olamaz.", ["24"]),
    ("İzin süresi 16, 20 ve 24 gündür.", ["16", "24"]),
])
def test_uydurulan_sayi_yakalanir(cevap, beklenen):
    """Gozlenen hata: kanun 'ondört/yirmi/yirmialtı' derken model
    '14 ... 24 gün' yazdi. Hukukta uydurulmus sure en tehlikeli hata."""
    from core.generate import sayilari_dogrula
    assert sayilari_dogrula(cevap, BAGLAM) == beklenen
