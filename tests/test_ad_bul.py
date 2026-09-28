"""Isim bulma katmaninin davranisi -- MODEL YUKLEMEDEN.

Gercek model olcumu ayri: `python olcum_ad.py` yedi belge turunde
19 gold isim uzerinde kosuyor (sabit sozluk 3/19, yerel model 19/19).
Burada olculen sey modelin zekasi degil, CEVRESINDEKI KOD: uydurmayi
eliyor mu, unvani kesiyor mu, kurum adini disarida birakiyor mu,
model coktugunde ne oluyor.

Sahte uretici kullaniliyor cunku gercek model 2,5 GB ve tek cagri
~10 saniye; test paketinin ona bagli olmamasi gerekiyor.
"""
from __future__ import annotations

import pytest

from core.ad_bul import adlari_bul
from core.generate import ModelYuklenemedi

METIN = """ANKARA 7. İŞ MAHKEMESİ'NE

DAVACI : Selahattin Kırımlıoğlu
VEKİLİ : Av. Nurhayat Özdemiroğlu
DAVALI : Yılmaz İnşaat Limited Şirketi

Tanık Zübeyde Karaoğlan beyanda bulunmuştur.
4857 sayılı İş Kanunu m.19 uygulanır."""


class SahteUretici:
    """Modelin yerine gecer: ne donecegi testte belirleniyor."""

    def __init__(self, cevap: str):
        self.cevap = cevap
        self.cagri = 0

    def kisa(self, istem, sistem=None, model=None, max_token=512):
        self.cagri += 1
        return self.cevap


def test_duz_liste_ayristiriliyor():
    u = SahteUretici("Selahattin Kırımlıoğlu\nZübeyde Karaoğlan")
    assert adlari_bul(METIN, u) == ["Selahattin Kırımlıoğlu", "Zübeyde Karaoğlan"]


def test_susleme_temizleniyor():
    """Kucuk modeller listelerini kalinlastirip madde isareti koyuyor."""
    u = SahteUretici("- **Selahattin Kırımlıoğlu**\n1. Zübeyde Karaoğlan")
    assert adlari_bul(METIN, u) == ["Selahattin Kırımlıoğlu", "Zübeyde Karaoğlan"]


def test_unvan_kesiliyor():
    """Istemde 'unvani yazma' yaziyor ama model bazen unutuyor.

    Unvan kalirsa maskeleme "Av. Nurhayat Ozdemiroglu" dizisini arar ve
    metinde baska yerde gecen unvansiz hali maskesiz kalir.
    """
    u = SahteUretici("Av. Nurhayat Özdemiroğlu")
    assert adlari_bul(METIN, u) == ["Nurhayat Özdemiroğlu"]


def test_uydurulan_ad_eleniyor():
    """EN ONEMLI TEST.

    Model metinde olmayan bir ad yazarsa maskeleme tablosuna girmemeli:
    tablo sismesi disinda, avukata "bu belgede Mehmet Yildiz var" diye
    yanlis bilgi verilmis olur.
    """
    u = SahteUretici("Selahattin Kırımlıoğlu\nMehmet Yıldız")
    assert adlari_bul(METIN, u) == ["Selahattin Kırımlıoğlu"]


def test_kanun_adi_eleniyor():
    """KORUNAN listesi kanun adlarini en bastan kesiyor."""
    u = SahteUretici("İş Kanunu\nSelahattin Kırımlıoğlu")
    assert adlari_bul(METIN, u) == ["Selahattin Kırımlıoğlu"]


def test_tek_kelime_eleniyor():
    """Soyadsiz tek kelime cogunlukla etiket ya da kurum parcasi."""
    u = SahteUretici("Davacı\nTanık\nSelahattin Kırımlıoğlu")
    assert adlari_bul(METIN, u) == ["Selahattin Kırımlıoğlu"]


def test_yok_cevabi_bos_liste():
    u = SahteUretici("YOK")
    assert adlari_bul(METIN, u) == []


def test_bos_metin_model_cagirmiyor():
    u = SahteUretici("Selahattin Kırımlıoğlu")
    assert adlari_bul("   ", u) == []
    assert u.cagri == 0, "bos metin icin model cagrilmamali"


def test_model_yuklenemezse_hata_yukseliyor():
    """Kurulum hatasi YUTULMAZ.

    Sessizce bos donmek "bu belgede isim yok" gibi gorunur -- gizlilik
    isinde en tehlikeli yanlis. Cagiran taraf (server.py) hatayi
    gunluge yaziyor ve maskeleme kalipli tanimlayicilarla devam ediyor.
    """
    class Cokuyor:
        def kisa(self, *a, **k):
            raise ModelYuklenemedi("model yok")

    with pytest.raises(ModelYuklenemedi):
        adlari_bul(METIN, Cokuyor())


def test_gecici_hata_parcayi_atliyor_ama_cokmuyor():
    """Tek parca patlarsa belge tumden maskesiz kalmamali."""
    class Kizgin:
        def kisa(self, *a, **k):
            raise RuntimeError("gecici")

    assert adlari_bul(METIN, Kizgin()) == []


def test_cok_gecen_ad_once_siralaniyor():
    u = SahteUretici("Zübeyde Karaoğlan\nZübeyde Karaoğlan\nSelahattin Kırımlıoğlu")
    assert adlari_bul(METIN, u)[0] == "Zübeyde Karaoğlan"
