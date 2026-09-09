"""Yuklenen belgeyi YERELDE metne cevirir ve maskelenecek adaylari onerir.

Bu modul disari hicbir sey gondermez. PDF ayristirma da, aday tespiti
de kullanicinin makinesinde calisir; Gemini'ye ancak maskelenmis metin
gider (bkz. core/maskele.py).

NORMALLESTIRME NEDEN SART

PDF'ten cikan metin kaynak metinle birebir ayni degil. Olculdu: PyMuPDF
ile uretilen bir dilekcede butun bosluklar KIRILMAZ BOSLUK (\\xa0) olarak
geldi:

    'DAVACI\\xa0\\xa0\\xa0:\\xa0Ahmet\\xa0Yılmaz\\xa0(T.C.\\xa010000000146)'

Regex'ler \\s sayesinde bunu yakaliyor ama isim maskeleme duz str.replace
kullaniyor: "Ahmet Yılmaz" ile "Ahmet\\xa0Yılmaz" eslesmez ve isim
SESSIZCE maskelenmeden disari giderdi. Gercek PDF'lerde bu ve benzeri
(yumusak tire, bagli harf, satir sonu bolunmesi) cok yaygin.
"""
from __future__ import annotations

import re
import unicodedata

# Sik gecen Turkce erkek/kadin adlari. Kapsamli degil ve olmasi da
# gerekmiyor: bu liste ADAY oneriyor, karari avukat veriyor. Amac
# avukatin isini kolaylastirmak, yerine gecmek degil.
ADLAR = {
    "ahmet", "mehmet", "mustafa", "ali", "hüseyin", "hasan", "ibrahim",
    "ismail", "osman", "yusuf", "murat", "ömer", "ramazan", "halil",
    "salih", "abdullah", "fatih", "mahmut", "recep", "kemal", "emre",
    "burak", "serkan", "volkan", "özkan", "cem", "can", "deniz", "berk",
    "onur", "kaan", "eren", "arda", "efe", "yiğit", "berkay", "tolga",
    "fatma", "ayşe", "emine", "hatice", "zeynep", "elif", "meryem",
    "şerife", "zehra", "sultan", "hanife", "merve", "özlem", "esra",
    "büşra", "kübra", "seda", "derya", "gamze", "pınar", "sevgi",
    "nurten", "leyla", "aslı", "ceren", "damla", "ebru", "gizem",
    "melike", "nazlı", "selin", "şule", "tuğba", "yasemin",
}

# BU KELIMELER ASLA MASKELENMEZ. Buyuk harf sezgisi Turk hukuk metninde
# cokuyor: "Is Kanunu", "Yargitay 9. Hukuk Dairesi", "Turk Borclar
# Kanunu" hepsi buyuk harfli. Biri maskelenirse sistem kanunu bulamaz
# ve kimse sebebini anlamaz -- sessiz ve olumcul.
KORUNAN = {
    "kanun", "kanunu", "kanunun", "madde", "maddesi", "yargıtay",
    "danıştay", "mahkeme", "mahkemesi", "hakimliğine", "hâkimliğine",
    "daire", "dairesi", "hukuk", "ceza", "iş", "asliye", "sulh",
    "bölge", "adliye", "bakanlık", "bakanlığı", "müdürlük", "müdürlüğü",
    "başkanlık", "başkanlığı", "cumhuriyet", "savcılık", "savcılığı",
    "türk", "türkiye", "borçlar", "medeni", "icra", "iflas", "esas",
    "karar", "sayılı", "davacı", "davalı", "vekili", "müvekkil",
    "müvekkilim", "konu", "adres", "telefon", "iban", "deliller",
    "sebepler", "açıklamalar", "sonuç", "istem", "talep", "tarihli",
}

# Adres: Turk adres yazimi yeterince kaliplı -- "Mah./Cad./Sok./Bulvar"
# ve genelde "No:" ile devam ediyor. Satirin kalanini aliyoruz cunku
# ilce/il sonda geliyor.
ADRES_RE = re.compile(
    # Bastaki 1-3 kelime alinıyor: "Ostim OSB Mah." derken ilk denemede
    # yalnizca "OSB Mah." yakalaniyor ve "Ostim" disarida kaliyordu.
    # [^\S\n] = satir sonu HARIC bosluk. \s+ kullanildiginda eslesme bir
    # onceki satirdan basliyor ve adayin icinde satir sonu kaliyordu;
    # aday tablosunda bosluklar tek bosluga indirildigi icin de metinde
    # bulunamiyor ve adres sessizce maskelenmeden kaliyordu.
    r"(?:[A-ZÇĞİÖŞÜ][\w./]*[^\S\n]+){1,3}(?:Mah\.|Mahallesi|Cad\.|Caddesi|"
    r"Sok\.|Sokak|Bulvarı|Bulvar|Blv\.)[^\n]*?(?:No\s*[:.]?\s*[\d/\-]+)[^\n]*")
# Ticaret unvani: "... A.Ş." / "... Ltd. Sti." gibi eklerle bitiyor.
# BAGLAC KELIMELER ZINCIRI KIRMAMALI. Ilk surumde her kelimenin buyuk
# harfle baslamasi isteniyordu; "Ornek Yapi Sanayi ve Ticaret A.S."
# unvaninda kucuk harfli "ve" zinciri kesti ve yalnizca "Ticaret A.S."
# maskelendi. Geriye "Ornek Yapi Sanayi ve" kaldi -- yani unvanin
# TANITICI kismi acikta. Kismi maskeleme, hic maskelememekten daha
# kotudur: korundugu sanilir.
KURUM_RE = re.compile(
    r"(?:[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü.]*|ve|ile)"
    r"(?:\s+(?:[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü.]*|ve|ile)){0,6}"
    r"\s+(?:A\.Ş\.|A\.S\.|Ltd\.\s*Şti\.|Ltd\.\s*Sti\.|Limited\s+Şirketi)")
TIRELI_SATIR_SONU = re.compile(r"(\w)-\n(\w)")
COK_BOSLUK = re.compile(r"[ \t]{2,}")
# "Ad Soyad": ilki bilinen bir ad, ikincisi buyuk harfle baslayan kelime.
AD_SOYAD = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+)\b")


def normalize(metin: str) -> str:
    """PDF'ten cikan metni tutarli hale getirir.

    Once yalnizca \\xa0 degistiriliyordu; NFKC eklendi cunku PDF'lerde
    bagli harfler (fi, fl) ve genislik varyantlari da geliyor ve bunlar
    "fesih" gibi kelimeleri arama icin bozuyor.
    """
    if not metin:
        return ""
    metin = unicodedata.normalize("NFKC", metin)
    metin = metin.replace("\xa0", " ").replace("­", "")   # kirilmaz bosluk, yumusak tire
    metin = TIRELI_SATIR_SONU.sub(r"\1\2", metin)              # satir sonu bolunmesi
    metin = COK_BOSLUK.sub(" ", metin)
    return "\n".join(s.rstrip() for s in metin.split("\n"))


def pdften_metin(veri: bytes) -> str:
    """PDF baytlarindan metin cikarir. Dosya diske YAZILMAZ."""
    import pymupdf

    with pymupdf.open(stream=veri, filetype="pdf") as belge:
        parcalar = [sayfa.get_text() for sayfa in belge]
    return normalize("\n".join(parcalar))


def metne_cevir(veri: bytes, ad: str) -> str:
    """Yuklenen dosyayi metne cevirir. Yalnizca PDF ve duz metin.

    Word/ODT bilerek disarida: bicim kutuphanesi eklemek kadar,
    icindeki gomulu nesnelerin (izlenen degisiklikler, yorumlar)
    beklenmedik kisisel veri tasimasi da risk.
    """
    dusuk = (ad or "").lower()
    if dusuk.endswith(".pdf"):
        return pdften_metin(veri)
    if dusuk.endswith((".txt", ".md")):
        for kodlama in ("utf-8", "cp1254", "latin-1"):
            try:
                return normalize(veri.decode(kodlama))
            except UnicodeDecodeError:
                continue
    raise ValueError("Yalnizca PDF ve TXT dosyalari okunabiliyor.")


def isim_adaylari(metin: str, en_fazla: int = 40) -> list[str]:
    """Maskelenmesi gereken isim ADAYLARINI onerir.

    Karar makineye birakilamiyor: Turkce isimlerin deseni yok ve buyuk
    harf sezgisi hukuk metninde cokuyor. Bu yuzden liste "kesin isim"
    degil "avukatin bakip onaylayacagi aday" olarak uretiliyor --
    KORUNAN kelimeler en bastan eleniyor ki kanun adlari listeye hic
    girmesin.
    """
    adaylar: dict[str, int] = {}
    for eslesme in AD_SOYAD.finditer(metin):
        ad, soyad = eslesme.group(1), eslesme.group(2)
        if ad.lower() in KORUNAN or soyad.lower() in KORUNAN:
            continue
        if ad.lower() not in ADLAR:
            continue
        tam = f"{ad} {soyad}"
        adaylar[tam] = adaylar.get(tam, 0) + 1
    return [a for a, _ in sorted(adaylar.items(), key=lambda x: -x[1])][:en_fazla]


def adres_adaylari(metin: str, en_fazla: int = 20) -> list[str]:
    """Adres gorunumlu satirlari onerir."""
    return _tekilles(m.group(0).strip() for m in ADRES_RE.finditer(metin))[:en_fazla]


def kurum_adaylari(metin: str, en_fazla: int = 20) -> list[str]:
    """Ticaret unvani gorunumlu diziler onerir.

    Sirket adi da tanimlayicidir: "Ornek Yapi A.S. calisanini savunmasi
    alinmadan cikardi" cumlesi hem sirketi hem dolayli olarak kisiyi
    isaret eder.
    """
    bulunan = []
    for m in KURUM_RE.finditer(metin):
        ad = re.sub(r"\s+", " ", m.group(0)).strip()
        # Bastaki etiket kelimesini at ("DAVALI : Ornek Yapi A.S.")
        ad = re.sub(r"^(?:%s)\s+" % "|".join(
            k.capitalize() for k in ("davalı", "davacı", "vekili")), "", ad,
            flags=re.IGNORECASE)
        if len(ad) > 6:
            bulunan.append(ad)
    return _tekilles(bulunan)[:en_fazla]


def _tekilles(dizi) -> list[str]:
    """Sirayi bozmadan yineleyenleri atar."""
    gorulen, sonuc = set(), []
    for x in dizi:
        if x not in gorulen:
            gorulen.add(x)
            sonuc.append(x)
    return sonuc


def adaylar(metin: str) -> dict[str, list[str]]:
    """Avukatin onayina sunulacak butun adaylar, turlerine gore."""
    return {
        "KISI": isim_adaylari(metin),
        "ADRES": adres_adaylari(metin),
        "KURUM": kurum_adaylari(metin),
    }
