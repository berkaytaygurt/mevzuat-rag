"""Dosya no, vergi no ve sasi numarasinin maskelenmesi.

NEDEN AYRI DOSYA

Bu uc alan once yalnizca core/sizinti.py'de vardi: ISARETLENIYOR ama
MASKELENMIYORLARDI. Sentetik bir dava dosyasiyla uctan uca olculdu, 12
gizli alandan ucu tam bu yuzden maskeli metinde kaldi. Isaretlemek
yetmiyor -- avukat maskeli metni oldugu gibi baska bir araca verirse
bunlar disari cikar.

IKI YONLU TEST

Testlerin yarisi "yakaladi mi", yarisi "FAZLA yakaladi mi" diye
bakiyor. Ikincisi en az birincisi kadar onemli: vergi no deseni sadece
"10 hane" demek, ciplak kullanilsa belgedeki her tutari, tarih dizisini
ve sayfa kodunu silerdi. O yuzden vergi no ve dosya no yalnizca ETIKETLI
ya da EKLI bicimde maskeleniyor.
"""
from __future__ import annotations

from core.maskele import Maske, sasi_gibi


def masked(metin: str) -> str:
    return Maske().maskele(metin)


# --------------------------- dosya numarasi ---------------------------

def test_dosya_no_etiketli_maskeleniyor():
    c = masked("DOSYA NO : 2026/1184 D.İş")
    assert "2026/1184" not in c
    assert "DOSYA NO" in c, "etiket kalmali, yoksa metin okunmaz olur"


def test_dosya_no_degisik_is_yakalaniyor():
    """D.Is EKSIKTI: sizinti.py yalnizca E./K./Esas/Karar taniyordu,

    oysa delil tespiti dosyalari tam olarak 'D.Is' diye numaralanir --
    yani en sik anonimlestirilecek dosya turu kaciyordu.
    """
    assert "2026/1184" not in masked("2026/1184 D.İş dosyasında")


def test_etiketsiz_esas_karar_numarasi_MASKELENMIYOR():
    """Ilk surumde maskeleniyordu ve YANLISTI -- mevcut test yakaladi.

    "YYYY/NNNN E." bicimi hukuk metninde neredeyse her zaman ATIF
    YAPILAN bir Yargitay kararidir:

        "Yargitay 9. HD 2019/1234 E. 2021/567 K. sayili karari"

    Bu kamuya acik bir karardir. Maskelenirse dilekcenin hukuki dayanagi
    silinir ve sistem karari bulamaz. Muvekkilin kendi dosyasi ise ya
    etiketli ("DOSYA NO : ...") ya da D.Is ekli gelir.

    Etiketsiz E./K. yine de core/sizinti.py'de ISARETLENIYOR; gizlemek
    isteyen avukat elle gizliyor.
    """
    atif = ("Yargıtay 9. Hukuk Dairesi 2019/1234 E. 2021/567 K. "
            "sayılı kararı gereğince")
    assert masked(atif) == atif


def test_etiketli_dosya_no_her_ekle_maskeleniyor():
    """Etiket varsa ek ne olursa olsun muvekkilin dosyasidir."""
    assert "2024/456" not in masked("Dosya No: 2024/456 E.")
    assert "2019/77" not in masked("DOSYA NO : 2019/77 K.")


def test_yil_bolu_sayi_tek_basina_maskelenmiyor():
    """Fazla maskeleme testi: ek ya da etiket yoksa dokunulmuyor."""
    metin = "2024/456 sayılı Bakanlar Kurulu kararı uyarınca"
    assert "2024/456" in masked(metin)


# ----------------------------- vergi no -------------------------------

def test_vergi_no_etiketli_maskeleniyor():
    assert "4820573916" not in masked("VERGİ NO : 4820573916")


def test_ciplak_on_hane_maskelenmiyor():
    """EN ONEMLI FAZLA-MASKELEME TESTI.

    Ciplak desen kullanilsaydi bu cumledeki tutar silinir, dilekce
    anlamsizlasirdi. Ciplak hali sizinti.py'de ISARETLENMEYE devam
    ediyor; karar avukatin.
    """
    metin = "Tutar 4820573916 TL olarak hesaplanmıştır."
    assert "4820573916" in masked(metin)


def test_vergi_no_telefon_desenine_kaptirilmiyor():
    """Telefon deseni 5 ile baslayan on haneli diziyi de esliyor.

    VERGI_NO_RE, TELEFON_RE'den ONCE calismazsa 5 ile baslayan bir vergi
    numarasi TEL yer tutucusunu alir; deger yine gizlenir ama TURU
    yanlis olur ve geri koyma tablosu bozulur.
    """
    m = Maske()
    c = m.maskele("VERGİ NO : 5820573916")
    assert "5820573916" not in c
    assert "VERGINO" in c and "TEL_" not in c


# ------------------------------- sasi ---------------------------------

def test_sasi_maskeleniyor():
    assert "VF1RJA00X67382914" not in masked("şasi numarası VF1RJA00X67382914 olup")


def test_on_yedi_haneli_duz_sayi_sasi_sayilmiyor():
    """Sasi numarasi HEM harf HEM rakam tasir; duz sayi tasimaz."""
    assert not sasi_gibi("12345678901234567")
    assert sasi_gibi("VF1RJA00X67382914")
    assert "12345678901234567" in masked("referans 12345678901234567 kodu")


# ------------------------- geri koyma butunlugu -----------------------

def test_maskelenen_degerler_geri_konabiliyor():
    """Maskeleme tek yonlu olsa avukat kendi belgesini geri alamaz."""
    ham = ("DOSYA NO : 2026/1184 D.İş\n"
           "VERGİ NO : 4820573916\n"
           "şasi VF1RJA00X67382914")
    m = Maske()
    geri = m.geri_koy(m.maskele(ham))
    assert "2026/1184" in geri
    assert "4820573916" in geri
    assert "VF1RJA00X67382914" in geri
