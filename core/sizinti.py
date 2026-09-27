"""Maskelemeden SONRA kalan tanitici izleri isaretler.

NEDEN AYRI BIR TARAMA

maskele.py kesin olani gizliyor: TC, IBAN, telefon, e-posta, plaka --
hepsinin ya saglamasi ya kaliplasmis bicimi var. Geriye KALIPSIZ ama
tanitici seyler kaliyor: arac marka/modeli, tescil tarihi, dosya esas
numarasi, sicil numarasi, az bilinen yer adi.

Bunlar desenle KESIN yakalanamaz; yakalanmaya calisilirsa ya yarisi
kacar ya metin delik desik olur. O yuzden bu modul MASKELEMIYOR,
yalnizca ISARETLIYOR -- karari avukat veriyor.

NEDEN YAPAY ZEKA DEGIL

Olculdu: yerel 3B modele "bu belgedeki kisisel verileri listele"
dendiginde belgeyi oldugu gibi geri kopyaladi, 29 saniyede sifir is
yapti. Buluta gondermek ise sorunun kendisi.

Asil sebep baska: bu iste YANLIS ALARMIN BEDELI 2 SANIYE, KACIRMANIN
BEDELI MUVEKKIL VERISI. Yani bilerek fazla isaretleyen, karari insana
birakan bir tarayici dogru alet; olasilikla calisan bir model degil.
"""
from __future__ import annotations

import re

# --- Kesin bicimli ama maskele.py'de olmayanlar -------------------
DESENLER = [
    # Mahkeme dosya numarasi: "2024/123 E." -- UYAP'ta davayi tek
    # basina bulmaya yetiyor, en tanitici kalinti bu.
    ("dosya numarası", re.compile(r"\b(20\d{2}|19\d{2})\s*/\s*\d{1,6}\s*(?:E\.?|K\.?|[Ee]sas|[Kk]arar)")),
    # Vergi kimlik no: 10 hane (TC 11 hane, o zaten maskeleniyor)
    ("vergi no", re.compile(r"(?<!\d)\d{10}(?!\d)")),
    # Sasi / VIN: 17 karakter, I-O-Q kullanilmaz
    ("şasi no", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")),
    # Dogum tarihi gorunumlu: "d.t. 12.03.1985" ya da "doğum"
    ("doğum tarihi", re.compile(r"(?:doğum|d\.?t\.?)[^\n]{0,20}?\d{1,2}[./]\d{1,2}[./]\d{4}", re.IGNORECASE)),
    # Sicil / ruhsat / police numarasi
    # Rakam SART: ilk surumde "[\w/-]{4,}" yaziyordu ve tek basina
    # "ruhsatında" kelimesini isaretliyordu -- gurultu, guveni bitirir.
    ("sicil/poliçe no", re.compile(r"(?:sicil|ruhsat|poliçe|police)\s*(?:no|numara(?:sı|si))\s*[:.]?\s*[\w/-]*\d[\w/-]*", re.IGNORECASE)),
    # IBAN disi hesap numarasi
    ("hesap no", re.compile(r"(?:hesap|iban)\s*(?:no|numara(?:sı|si))?\s*[:.]?\s*[\d\s-]{10,}", re.IGNORECASE)),
]

# --- Kalipsiz ama tanitici: buyuk harfle baslayan diziler ----------
# Hukuk metninde her onemli sey buyuk harfli oldugu icin bu liste
# SADECE ONERI. Korunan kelimeler en bastan eleniyor.
BUYUK_DIZI = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}){0,3})\b")

# Hukuk metninin kendi kelimeleri -- isaretlenirse gurultu olur.
YOKSAY = {
    "kanun", "kanunu", "kanunun", "madde", "maddesi", "yargıtay", "danıştay",
    "mahkeme", "mahkemesi", "hakimliğine", "hâkimliğine", "daire", "dairesi",
    "hukuk", "ceza", "asliye", "sulh", "bölge", "adliye", "bakanlık",
    "bakanlığı", "müdürlük", "müdürlüğü", "başkanlık", "başkanlığı",
    "cumhuriyet", "savcılık", "savcılığı", "türk", "türkiye", "borçlar",
    "medeni", "icra", "iflas", "esas", "karar", "sayılı", "davacı", "davalı",
    "vekili", "müvekkil", "müvekkilim", "müvekkilin", "konu", "adres",
    "telefon", "deliller", "sebepler", "açıklamalar", "sonuç", "istem",
    "talep", "tarihli", "tüketici", "hakem", "heyeti", "bilirkişi", "tanık",
    "ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz",
    "ağustos", "eylül", "ekim", "kasım", "aralık",
    # Etiket kelimeleri: satir basinda buyuk harfle yaziliyorlar ama
    # kendileri tanitici degil, yanlarindaki deger tanitici.
    "dosya", "şasi", "sasi", "motor", "marka", "model", "plaka",
    "sayfa", "ekler", "not", "ilgili", "sayın",
}

# Yer tutucularin kendisi ("[KISI_1]") isaretlenmesin
YER_TUTUCU = re.compile(r"\[[A-Z]+_\d+\]")

EN_FAZLA_ONERI = 25


def _baglam(metin: str, bas: int, son: int, yaricap: int = 45) -> str:
    a = max(0, bas - yaricap)
    b = min(len(metin), son + yaricap)
    return ("…" if a > 0 else "") + metin[a:b].replace("\n", " ").strip() + ("…" if b < len(metin) else "")


def _korunani_ayikla(dizi: str) -> list[str]:
    """Diziden korunan kelimeleri atip kalan bitisik obekleri doner.

    "Tanık Zübeyde Karaoğlan" -> ["Zübeyde Karaoğlan"]
    "Müvekkil Beypazarı"      -> ["Beypazarı"]
    """
    obekler, simdiki = [], []
    for kelime in dizi.split():
        if kelime.lower() in YOKSAY:
            if simdiki:
                obekler.append(" ".join(simdiki))
                simdiki = []
        else:
            simdiki.append(kelime)
    if simdiki:
        obekler.append(" ".join(simdiki))
    return obekler


def tara(metin: str) -> dict:
    """Maskeli metinde kalan tanitici izleri isaretler.

    Doner: {"kesin": [...], "olasi": [...]}
      kesin : bicimi belli, muhtemelen gizlenmeli
      olasi : buyuk harfli dizi, isim/marka/yer olabilir -- KARAR SENIN
    """
    metin = metin or ""
    temiz = YER_TUTUCU.sub(" ", metin)

    kesin, gorulen = [], set()
    for ad, desen in DESENLER:
        for m in desen.finditer(temiz):
            deger = m.group(0).strip()
            if deger.lower() in gorulen:
                continue
            gorulen.add(deger.lower())
            kesin.append({"tur": ad, "deger": deger,
                          "baglam": _baglam(temiz, m.start(), m.end())})

    olasi, sayac = [], {}
    for m in BUYUK_DIZI.finditer(temiz):
        # KORUNAN KELIME BUTUN DIZIYI ELEMEMELI. Ilk surum boyleydi ve
        # "Tanık Zübeyde Karaoğlan" dizisinde "tanık" korunan oldugu
        # icin ISMI DE birlikte atiyordu -- yani tam yakalamasi gereken
        # seyi kaciriyordu. Simdi korunanlar ayiklanip kalan bitisik
        # obekler ayri ayri degerlendiriliyor.
        for dizi in _korunani_ayikla(m.group(1)):
            if len(dizi) < 4:
                continue
            sayac[dizi] = sayac.get(dizi, 0) + 1
            if sayac[dizi] == 1:
                olasi.append({"deger": dizi,
                              "baglam": _baglam(temiz, m.start(), m.end())})

    # Cok gecen diziler once: belgede tekrar eden bir ad, tek gecen bir
    # kelimeden daha buyuk olasilikla taraf ya da marka adidir.
    olasi.sort(key=lambda x: -sayac.get(x["deger"], 0))
    for o in olasi:
        o["gecis"] = sayac.get(o["deger"], 1)

    return {
        "kesin": kesin[:EN_FAZLA_ONERI],
        "olasi": olasi[:EN_FAZLA_ONERI],
        "ozet": {"kesin": len(kesin), "olasi": len(olasi)},
    }
