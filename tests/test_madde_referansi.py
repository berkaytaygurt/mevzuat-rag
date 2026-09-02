"""Avukatin yazdigi madde atiflarinin dogru kanuna baglandigini denetler.

NEDEN VAR
Avukatin en sik yaptigi arama bu: "TBK 344", "4857 madde 19", "Is Kanunu
19. madde". Olculdu -- hepsi YANLIS kanunun ayni numarali maddesini
getiriyordu:

    "4857 madde 19"  -> 5285 m.19
    "TMK 166"        -> 5905 m.166
    "TBK 344"        -> 6102 m.344

Iki ayri sebep vardi:
1. Kanun ancak "sayili" kelimesi varsa taniniyordu; kisaltma listesi de
   kanun ADLARINI ("Is Kanunu") hic icermiyordu.
2. Kanun taninamayinca kod yalnizca madde numarasina bakip rastgele bir
   kanunun maddesini donduruyordu -- ustelik bu yol RRF'te en yuksek
   agirligi (3.0) tasidigi icin dogruca 1. siraya cikiyordu.
"""
from core.retrieve import Retriever


def coz(soru: str) -> tuple[str | None, str | None]:
    kanun, sonu = Retriever._kanun_bul(soru)
    return kanun, Retriever._madde_bul(soru, sonu)


def test_numarali_atif():
    assert coz("4857 madde 19") == ("4857", "19")
    assert coz("6098 sayılı kanun madde 344") == ("6098", "344")


def test_kisaltmali_atif():
    assert coz("TBK 344") == ("6098", "344")
    assert coz("TCK m.125") == ("5237", "125")
    assert coz("TMK 166 maddesi") == ("4721", "166")


def test_kanun_adiyla_atif():
    assert coz("İş Kanunu 19. madde") == ("4857", "19")
    assert coz("türk medeni kanunu 166. madde") == ("4721", "166")
    # Uzun ad kisa adi ezmeli: "türk ceza kanunu" != "ceza kanunu" degil ama
    # ikisi de ayni numaraya gitmeli
    assert coz("türk ceza kanunu 125. madde") == ("5237", "125")


def test_harf_ekli_madde():
    assert coz("2576 madde 3/A") == ("2576", "3/A")
    assert coz("2576 m.3/a") == ("2576", "3/A")


def test_gecici_ve_ek_madde():
    assert coz("4857 geçici madde 6") == ("4857", "Geçici 6")
    assert coz("4857 ek madde 2") == ("4857", "Ek 2")


def test_kanun_belirtilmemisse_madde_yolu_kullanilmaz():
    """Kanun bilinmiyorsa dogrudan madde yolu susmali.

    Eskiden ayni numarayi tasiyan rastgele bir kanunun maddesi donuyordu.
    """
    kanun, madde = coz("madde 19")
    assert kanun is None
    r = Retriever.__new__(Retriever)          # store/embedder gerekmiyor
    assert r._dogrudan_madde("madde 19") == []


def test_duz_soruda_madde_yolu_tetiklenmiyor():
    assert coz("yıllık ücretli izin süresi")[1] is None
    assert coz("kira bedelinin belirlenmesi")[1] is None
