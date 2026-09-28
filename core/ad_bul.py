"""Kisi adlarini yerel modele BULDURUR -- maskeletmez.

NEDEN AYRI BIR KATMAN

core/belge.py'deki isim_adaylari() ilk adin 71 kisilik sabit ADLAR
sozlugunde olmasini sart kosuyor. Turkce isimleri sabit listeyle
kapsamak mumkun degil; sentetik bir dava dosyasiyla olculdu, 12 gizli
alandan ucu (davaci, vekil, tanik) tam bu yuzden maskeli metinde kaldi:

    Selahattin Kırımlıoğlu, Av. Nurhayat Özdemiroğlu, Zübeyde Karaoğlan

Desen de ise yaramiyor: hukuk metninde her onemli sey buyuk harfle
yazilir (MAHKEMESI, DAVACI, Turk Borclar Kanunu), o yuzden buyuk harf
sezgisi coker.

MODELE "MASKELE" DENMIYOR, "BUL" DENIYOR

Bu ayrim olculdu. Yerel modele "bu metni maskele" dendiginde belgeyi
oldugu gibi geri yaziyordu -- metni yeniden yazmak kucuk bir modelin en
kotu oldugu is. Burada model TEK BIR SEY yapiyor: gecen adlari
listeliyor. Degistirme islemini core/maskele.py yapiyor, deterministik
olarak. Model tek kelime metin uretmiyor.

UYDURMAYA KARSI KORUMA

Modelin dondurdugu her ad METINDE ARANIYOR; bulunamayan atiliyor.
Model olmayan bir ismi uydurursa maskeleme tablosuna girmiyor. Bu
kontrol ucuz ve uydurmanin en yaygin bicimini kesiyor.

NE YAPMAZ

Kesin cozum degil. Model bir ismi kacirabilir; o yuzden sonuc yine
avukatin onayina cikiyor ve core/sizinti.py maskelemeden SONRA bir kez
daha tariyor. Uc katman ayni seye bakiyor cunku kacirmanin bedeli
muvekkil verisi.
"""
from __future__ import annotations

import logging
import re

from .belge import KORUNAN, normalize
from .generate import ModelYuklenemedi

log = logging.getLogger(__name__)

SISTEM = """Sen bir belge tarama aracısın. Sana bir hukuk belgesinden
bir bölüm verilir. Sen o bölümde geçen KİŞİ ADLARINI listelersin.

Kurallar:
1. Her satıra bir ad yaz. Başka hiçbir şey yazma, açıklama yapma.
2. Adı belgede yazdığı gibi yaz; harfini değiştirme, çevirme.
3. Yalnızca GERÇEK KİŞİ adları: davacı, davalı, vekil, tanık, bilirkişi,
   müvekkil, imza sahibi.
4. Kurum, şirket, mahkeme, daire, kanun adı YAZMA.
5. Şehir, ilçe, mahalle, cadde adı YAZMA.
6. Unvanı değil adın kendisini yaz: "Av. Ayşe Yılmaz" için "Ayşe Yılmaz".
7. Bölümde hiç kişi adı geçmiyorsa yalnızca YOK yaz."""

ISTEM = """Bölüm:
{parca}

Bu bölümde geçen kişi adlarını satır satır yaz."""

# Parca boyu: modelin baglami 8192 token ama uzun metinde dikkat
# dagiliyor ve ortadaki adlar atlaniyor. 2500 karakter bir dilekce
# sayfasindan biraz fazla; paragraf sinirinda bolunuyor.
PARCA_BOYU = 2500

# Modelin satir basina koydugu suslemeler: "- ", "1. ", "* ", "**"
_SUS = re.compile(r"^\s*(?:\d+[.)]\s*|[-*•]\s*)|[*_]{1,3}")
# Unvanlar: model 6. kurali bazen unutuyor, deterministik olarak kesiyoruz.
_UNVAN = re.compile(
    r"^(?:Av\.?|Avukat|Dr\.?|Doç\.?|Prof\.?|Sn\.?|Sayın|Bay|Bayan)\s+",
    re.IGNORECASE)


def _parcala(metin: str) -> list[str]:
    """Metni paragraf sinirinda PARCA_BOYU'na yakin parcalara boler."""
    parcalar, simdiki = [], ""
    for paragraf in re.split(r"\n\s*\n", metin):
        if simdiki and len(simdiki) + len(paragraf) > PARCA_BOYU:
            parcalar.append(simdiki)
            simdiki = paragraf
        else:
            simdiki = (simdiki + "\n\n" + paragraf) if simdiki else paragraf
    if simdiki.strip():
        parcalar.append(simdiki)
    return parcalar or [metin]


def _temizle(satir: str) -> str:
    ad = _SUS.sub("", satir).strip()
    ad = _UNVAN.sub("", ad).strip()
    return ad.strip(" .,:;\"'()[]")


def _gecerli(ad: str, metin_katlanmis: str) -> bool:
    """Ad gercekten metinde geciyor ve korunan bir kelime degil mi."""
    if not (3 <= len(ad) <= 60):
        return False
    if ad.upper().startswith("YOK"):
        return False
    parcalar = ad.split()
    if not (1 < len(parcalar) <= 4):
        # Tek kelimelik "ad" cogunlukla etiket ya da kurum parcasi
        # ("Davacı", "Mahkemesi"); soyadsiz ad maskelemeye deger de degil.
        return False
    if any(p.lower() in KORUNAN for p in parcalar):
        return False
    # UYDURMA KONTROLU: modelin yazdigi ad metinde gecmiyorsa atilir.
    return _katla(ad) in metin_katlanmis


def _katla(s: str) -> str:
    """Karsilastirma icin bosluklari tekilleyip kucultur.

    SIRA ONEMLI: once İ/I katlaniyor, sonra kucultuluyor. Python'da
    "İ".lower() "i" + birlesen nokta (U+0307) veriyor ve karsilastirma
    sessizce basarisiz oluyor.
    """
    s = re.sub(r"\s+", " ", normalize(s)).strip()
    return s.replace("İ", "i").replace("I", "ı").lower()


def adlari_bul(metin: str, uretici, en_fazla: int = 25) -> list[str]:
    """Metinde gecen kisi adlarini doner; bulunamazsa bos liste.

    Model yuklenemiyorsa hata YUKSELIYOR: bu bir kurulum sorunu ve
    sessizce bos donmek "belgede isim yok" gibi gorunur -- gizlilik
    isinde en tehlikeli yanlis.
    """
    if not metin or not metin.strip():
        return []

    katlanmis = _katla(metin)
    bulunan: dict[str, int] = {}

    for parca in _parcala(metin):
        try:
            c = uretici.kisa(ISTEM.format(parca=parca), sistem=SISTEM,
                             max_token=200)
        except ModelYuklenemedi:
            raise
        except Exception as exc:
            log.warning("ad bulunamadi (parca atlandi): %s", str(exc)[:80])
            continue

        for satir in (c or "").split("\n"):
            ad = _temizle(satir)
            if _gecerli(ad, katlanmis):
                bulunan[ad] = bulunan.get(ad, 0) + 1

    # Cok gecen once: belgede tekrar eden ad daha onemli bir taraftir.
    sirali = sorted(bulunan, key=lambda a: (-bulunan[a], a))
    return sirali[:en_fazla]
