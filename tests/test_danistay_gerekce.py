"""Danistay kararindan gerekce bolumunun ayiklanmasini denetler.

NEDEN VAR
Danistay karari uzun bir usul basligiyla basliyor ve icindeki isimler
zaten anonimlestirilmis:

    İSTEMİN KONUSU : ... Bölge İdare Mahkemesi ... tarih ve E:...,
    K:... sayılı ısrar kararının temyizen incelenerek bozulması
    istenilmektedir.

Bu paragraflarda bilgi yok. Eleme modeli metnin BASINI okudugu icin
kararin ozunu hic gormuyor ve alaka puani cok dusuk cikiyordu --
olculdu, Danistay kararlari 0,03-0,17 alirken Yargitay kararlari
0,999 aliyordu. Ayni havuzda birlestirilince Danistay hep dibe
gomuluyordu, yani idari yargi fiilen gorunmez kaliyordu.

YARGITAY'DA AYNI TEKNIK REDDEDILMISTI (karar_parser modul aciklamasi):
aranan isaret 15 kararin hicbirinde yoktu. Danistay farkli; onbellekteki
56 kararda olculdu:

    GEREĞİ GÖRÜŞÜLDÜ        56/56   (%100)
    HUKUKİ DEĞERLENDİRME    50/56   (%89)

Ayni teknigin bir arsivde yanlis, otekinde dogru olmasi tuhaf degil:
iki mahkemenin karar yazim gelenegi ayri.
"""
from scraper.karar_parser import danistay_gerekce

USUL = ("İSTEMİN KONUSU : ... Bölge İdare Mahkemesi ... tarih ve E:..., "
        "K:... sayılı ısrar kararının temyizen incelenerek bozulması "
        "istenilmektedir. YARGILAMA SÜRECİ : Dava konusu istem: ... ")
OZ = ("Kamu görevlisine disiplin cezası verilebilmesi için soruşturma "
      "yapılması ve savunma alınması zorunludur. " * 6)


def test_hukuki_degerlendirmeden_baslatiyor():
    metin = USUL + "HUKUKİ DEĞERLENDİRME : " + OZ
    sonuc = danistay_gerekce(metin)
    assert sonuc.startswith("HUKUKİ DEĞERLENDİRME")
    assert "İSTEMİN KONUSU" not in sonuc


def test_geregi_gorusulduden_baslatiyor():
    """Kararlarin %100'unde bulunan isaret."""
    metin = USUL + "GEREĞİ GÖRÜŞÜLDÜ : " + OZ
    sonuc = danistay_gerekce(metin)
    assert sonuc.startswith("GEREĞİ GÖRÜŞÜLDÜ")


def test_isaret_yoksa_metne_dokunmuyor():
    """Kirpmak, YANLIS YERDEN kirpmaktan iyidir.

    Yargitay tarafinda tam bu hata yapilmisti: isaret bulunamayinca kod
    "metnin ikinci yarisini al" yedegine dusuyor ve gerekcenin basini
    kesiyordu.
    """
    metin = USUL + OZ
    assert danistay_gerekce(metin) == metin


def test_isaret_metnin_sonundaysa_kirpmiyor():
    """Isaret gecerken degil, BASLIK olarak gecmeli.

    Karar metninin son cumlesinde "gereği görüşüldü" gecerse ve oradan
    kesersek elimizde birkac kelime kalir. Kalan cok kisaysa tam metne
    donuluyor.
    """
    metin = OZ + " ... gereği görüşüldü."
    assert danistay_gerekce(metin) == metin


def test_bos_metin_cokmuyor():
    assert danistay_gerekce("") == ""
    assert danistay_gerekce(None) is None


def test_buyuk_kucuk_harf_farki_onemsiz():
    metin = USUL + "Hukuki Değerlendirme: " + OZ
    assert danistay_gerekce(metin).lower().startswith("hukuki değerlendirme")
