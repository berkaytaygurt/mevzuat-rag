"""Madde -> madde atif grafi.

NEDEN VAR
Bir madde tek basina okunamaz: "Bu Kanun, 4 uncu Maddedeki istisnalar
disinda ..." diyen hukmu m.4'e bakmadan anlamak mumkun degil. Vektor
aramasi bu bagi goremez; m.1'i getirir, m.4'ten haberi olmaz.

Olculdu (Is Kanunu, 137 madde): 53 maddede atif var, 155 kenar.
"""
from core.atif_grafi import AtifGrafi, grafi_kur, maddeden_atiflar


def madde(metin, no="4857", madde_no="1"):
    return {"metin": metin, "mevzuat_no": no, "madde_no": madde_no}


def test_kendi_kanunundaki_maddeye_atif():
    k = maddeden_atiflar(madde(
        "Bu Kanun, 4 üncü Maddedeki istisnalar dışında kalan işyerlerine uygulanır."))
    assert len(k) == 1
    assert k[0]["hedef"] == "4857-4"
    assert k[0]["iliski"] == "istisna"


def test_baska_kanuna_atif():
    k = maddeden_atiflar(madde(
        "2821 sayılı Sendikalar Kanununun 31 inci maddesi hükümleri saklıdır.",
        madde_no="5"))
    assert any(x["hedef"] == "2821-31" for x in k), k


def test_sayi_zinciri():
    """'68, 69 ve 70 inci maddeler' uc ayri kenar uretmeli."""
    k = maddeden_atiflar(madde(
        "68, 69 ve 70 inci maddeler hükümleri uygulanır.", madde_no="71"))
    hedefler = {x["hedef"] for x in k}
    assert hedefler == {"4857-68", "4857-69", "4857-70"}, hedefler


def test_kendi_kendine_atif_atiliyor():
    k = maddeden_atiflar(madde("Bu maddenin 1 inci fıkrası uyarınca...",
                               madde_no="1"))
    assert not [x for x in k if x["hedef"] == "4857-1"]


def test_iliski_turu_belirleniyor():
    turler = {}
    for metin, no in (
        ("3 üncü maddesindeki yükümlülüğe aykırı davranan işverene para cezası verilir.", "3"),
        ("5 inci maddesi hükümleri uygulanır.", "5"),
        ("7 nci maddesi yürürlükten kaldırılmıştır.", "7"),
    ):
        k = maddeden_atiflar(madde(metin, madde_no="98"))
        if k:
            turler[no] = k[0]["iliski"]
    assert turler.get("3") == "yaptirim", turler
    assert turler.get("7") == "mulga", turler


def test_kanit_cumlesi_tasiniyor():
    """Kullaniciya baglantinin gerekcesi gosterilmeli, uretilmis ozet degil."""
    k = maddeden_atiflar(madde(
        "Bu Kanun, 4 üncü Maddedeki istisnalar dışında uygulanır."))
    assert "4 üncü Madde" in k[0]["kanit"]


def test_ileri_ve_geri_dizin(tmp_path):
    kayitlar = [
        madde("Bu Kanun, 4 üncü Maddedeki istisnalar dışında uygulanır.", madde_no="1"),
        madde("3 üncü maddesindeki yükümlülüğe aykırı davranana ceza verilir.",
              madde_no="98"),
    ]
    g = grafi_kur(kayitlar)
    assert "4857-1" in g["ileri"]
    assert "4857-4" in g["geri"]
    assert g["geri"]["4857-4"] == ["4857-1"]


def test_graf_yoksa_site_calismaya_devam_eder(tmp_path):
    g = AtifGrafi(tmp_path / "yok.json")
    assert g.hazir_mi() is False
    assert g.atiflar("4857", "19") == []
    assert g.atif_yapanlar("4857", "19") == []


def test_kanit_her_zaman_atfi_iceriyor():
    """Kanit cumlesi, kanitlamasi gereken atfi ICERMELI.

    Onceki surum cumle basindan baslayip sabit uzunlukta kirpiyordu.
    Hukuk metninde "a)", "f)" bent isaretleri ve tarihlerdeki noktalar
    cumle sinirini yanlis yerde buluyor; uzun bir liste cumlesi cikiyor
    ve kirpma atfa varmadan bitiyordu. Ekranda "4857 sayili Kanunun 25
    inci maddesi" yazmasi gereken yerde onun oncesindeki bent listesi
    gorunuyordu.
    """
    uzun = ("a) Kaçakçılık, vergi kaçakçılığı veya haksız mal edinme "
            "suçlarından mahkûm olmamak, f) Görevini devamlı yapmasına engel "
            "herhangi bir özrü bulunmamak, g) Birlikler ve TİM dahil, herhangi "
            "bir işyerinden, 4857 sayılı İş Kanununun 25 inci maddesinin "
            "birinci fıkrasının ikinci bendinde belirtilen nedenlerle işten "
            "çıkarılmamış olmak")
    k = maddeden_atiflar({"metin": uzun, "mevzuat_no": "13399", "madde_no": "8"})
    assert k, "atif bulunamadi"
    kanit = k[0]["kanit"]
    assert "25 inci madde" in kanit, kanit
    assert len(kanit) < 260, len(kanit)


def test_kisa_cumle_oldugu_gibi_kaliyor():
    k = maddeden_atiflar(madde(
        "Bu Kanun, 4 üncü Maddedeki istisnalar dışında uygulanır."))
    assert not k[0]["kanit"].startswith("…")


def test_dort_haneli_madde_numarasi():
    """Turk Ticaret Kanunu 1535, Turk Medeni Kanunu 1030 maddelik.

    Onceki surum en fazla 3 hane okuyor ve sol tarafi sinirlamadigi icin
    "1201 inci maddeye" ifadesinden "201" cikariyordu -- yani dort haneli
    maddeler yanlis maddelere baglaniyordu.
    """
    k = maddeden_atiflar(madde(
        "bu navlunu teminat altına almak üzere 1201 inci maddeye göre "
        "tanınan hapis hakkına sahiptir.", no="6102", madde_no="1136"))
    assert [e["hedef"] for e in k] == ["6102-1201"], k


def test_uc_haneli_madde_bozulmadi():
    k = maddeden_atiflar(madde("344 üncü maddesi uyarınca.", no="6098",
                               madde_no="1"))
    assert [e["hedef"] for e in k] == ["6098-344"], k
