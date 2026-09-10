"""Atif denetimi.

Bu ozelligin butun degeri DOGRULUGUNDA: avukat "denetlendi" yazisini
gorup guvenecek. Yanlis "tamam" demek, hic denetlememekten kotudur.
"""
from __future__ import annotations

from core.denetim import Denetci, _ad_cozumle

# Kucuk sahte kulliyat: gercek depoyu yuklemek 30 saniye suruyor ve
# testin olctugu sey depo degil, denetim mantigi.
KAYITLAR = [
    {"mevzuat_no": "4857", "mevzuat_adi": "İŞ KANUNU", "madde_no": "19",
     "baslik": "Sözleşmenin feshinde usul", "metin": "İşveren fesih bildirimini…",
     "mulga": False, "kismi_mulga": False, "degisiklikler": ""},
    {"mevzuat_no": "4857", "mevzuat_adi": "İŞ KANUNU", "madde_no": "17",
     "baslik": "Süreli fesih", "metin": "Belirsiz süreli iş sözleşmelerinin…",
     "mulga": False, "kismi_mulga": False, "degisiklikler": ""},
    {"mevzuat_no": "6102", "mevzuat_adi": "TÜRK TİCARET KANUNU",
     "madde_no": "148", "baslik": "", "metin": "(Mülga)",
     "mulga": True, "kismi_mulga": False, "degisiklikler": ""},
    {"mevzuat_no": "6102", "mevzuat_adi": "TÜRK TİCARET KANUNU",
     "madde_no": "149", "baslik": "İnceleme hakkı", "metin": "…",
     "mulga": False, "kismi_mulga": True, "degisiklikler": ""},
]


def _denetci():
    return Denetci(KAYITLAR)


def test_kanun_adi_numaraya_cevriliyor():
    assert _ad_cozumle("4857") == "4857"
    assert _ad_cozumle("İş Kanunu") == "4857"
    assert _ad_cozumle("Türk Borçlar Kanunu") == "6098"
    assert _ad_cozumle("4857 sayılı İş Kanunu") == "4857"
    assert _ad_cozumle("Uydurma Mevzuat") is None


def test_gecerli_atif_tamam_diyor():
    r = _denetci().denetle("4857 sayılı İş Kanunu m.19 uyarınca…")
    assert r["ozet"]["tamam"] == 1
    a = r["atiflar"][0]
    assert a["durum"] == "tamam"
    assert a["baslik"] == "Sözleşmenin feshinde usul"
    assert a["metin"], "gercek madde metni verilmeli"


def test_olmayan_madde_yakalaniyor():
    """Uydurma madde numarasi -- dil modelinin en sik hatasi."""
    r = _denetci().denetle("4857 sayılı İş Kanunu m.999 uyarınca…")
    a = r["atiflar"][0]
    assert a["durum"] == "bulunamadi"
    assert "bulunamadı" in a["not_"]


def test_mulga_madde_yakalaniyor():
    """Yururlukten kalkmis maddeye dayanan dilekce mahkemede utandirir."""
    r = _denetci().denetle("6102 sayılı Türk Ticaret Kanunu m.148 gereğince…")
    a = r["atiflar"][0]
    assert a["durum"] == "mulga"
    assert "yürürlükten" in a["not_"]


def test_kismi_mulga_ayirt_ediliyor():
    r = _denetci().denetle("6102 sayılı Kanun m.149 uyarınca…")
    assert r["atiflar"][0]["durum"] == "kismi_mulga"


def test_bilinmeyen_kanun_uydurulmuyor():
    """Kanun cozumlenemiyorsa "tamam" DENMEZ; belirsiz denir."""
    r = _denetci().denetle("Uydurma Mevzuat Kanunu m.12 uyarınca…")
    if r["atiflar"]:
        assert r["atiflar"][0]["durum"] in ("kanun_yok", "bulunamadi")
        assert r["atiflar"][0]["durum"] != "tamam"


def test_karar_atiflari_dogrulanmis_gibi_gosterilmiyor():
    """Kararlar kulliyatta yok; "denetlendi" demek yaniltici olurdu.

    Uydurma karar numarasi hukukta en sik gorulen yapay zeka hatasi;
    kullanici bunun denetlenmedigini BILMELI.
    """
    r = _denetci().denetle(
        "Yargıtay 9. Hukuk Dairesi 2019/1234 E. 2021/567 K. sayılı kararı…")
    assert len(r["kararlar"]) == 1
    assert r["kararlar"][0]["esas"] == "2019/1234"
    assert r["kararlar"][0]["karar"] == "2021/567"
    assert r["kararlar"][0]["durum"] == "denetlenmedi"


def test_ayni_atif_bir_kez_listeleniyor():
    r = _denetci().denetle(
        "4857 m.19 ... yine 4857 sayılı İş Kanunu m.19 ... tekrar m.19")
    assert r["ozet"]["toplam"] == 1


def test_iddiaya_yorum_yapilmiyor():
    """Modul "bu madde iddiani desteklemiyor" DEMEZ.

    Oyle bir yargi hukuki degerlendirmedir ve olculen dogruluk onu
    tasimaz. Gercek metni verip karari avukata birakiyoruz.
    """
    r = _denetci().denetle("4857 sayılı İş Kanunu m.17 uyarınca…")
    a = r["atiflar"][0]
    assert a["not_"] == ""          # gecerli atifta yorum yok
    assert a["metin"]               # ama metin var, avukat karsilastirir


def test_bos_metin_cokmuyor():
    r = _denetci().denetle("")
    assert r["ozet"]["toplam"] == 0
    assert r["kararlar"] == []
