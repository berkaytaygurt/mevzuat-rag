"""Madde -> madde atif grafi: kanunun kendi metnindeki caprazlar.

NE ISE YARIYOR
Bir madde tek basina okunamaz. "Bu Kanun, 4 uncu Maddedeki istisnalar
disinda ..." diyen bir hukmu, m.4'e bakmadan anlamak mumkun degil. Klasik
vektor aramasi bu bagi goremez: m.1'i getirir, m.4'ten haberi olmaz.

Mevcut core/atif_zinciri.py KARAR -> MADDE yonunde calisiyor (hangi karar
hangi maddeyi yorumlamis). Bu modul farkli bir sey yapiyor: KANUN METNININ
KENDISININ baska maddelere yaptigi atiflari cikariyor ve ILISKI TURUNU de
belirliyor.

    4857-1  --istisna-->   4857-4    "Bu Kanun, 4 uncu Maddedeki istisnalar disinda..."
    4857-5  --istisna-->   2821-31   "2821 sayili Sendikalar Kanununun 31 inci maddesi saklidir."
    4857-98 --yaptirim-->  4857-3    "...3 uncu maddesindeki yukumluluge aykiri davranan isveren..."

OLCULDU (Is Kanunu, 137 madde): 53 maddede (%39) atif var, 155 kenar --
132'si kanun ici, 23'u disa. Iliski turleri: atif 47, gonderme 44,
yaptirim 33, istisna 23, degistirir 5.

NEDEN GRAF VERITABANI YOK
Bu olcekte gereksiz. Sonuc duz bir sozluk olarak diske yaziliyor, tipki
atif_zinciri.json gibi. Neo4j kurmak kurulum ve bakim yuku getirir,
karsiliginda bir sey vermez.

YONTEM NOTU
Regex'i "sayi zinciri + madde" olarak tek parcada yazmak katastrofik geri
izlemeye yol aciyor (ic ice yildiz). Bunun yerine once "madde" kelimesine
capa atilip GERIYE dogru sayi zinciri okunuyor: "68, 69 ve 70 inci
maddeler" -> [70, 69, 68]. Geri izleme riski yok, sure metin uzunluguyla
dogru orantili.
"""
from __future__ import annotations

import json
import re
from collections import Counter

# Turkce sira eki: 1 inci, 2 nci, 3 uncu, 4 uncu, 6 nci, 9 uncu, 40 inci...
ORD = r"(?:inci|ıncı|uncu|üncü|nci|ncı|ncu|ncü)"

# "madde" kelimesinin cekimli halleri
MADDE_KEL = re.compile(
    r"[Mm]adde(?:sinin|lerinde|lerine|sine|leri|lerde|ler|sini|si|de|ye|yi|nin)?")

# Capadan GERIYE okunacak parcalar
# (?<!\d) ve 1-4 hane SART: onceki surum en fazla 3 hane okuyordu ve
# sol tarafi sinirlamadigi icin "1201 inci maddeye" ifadesinden "201"
# cikariyordu. Turk Ticaret Kanunu 1535, Turk Medeni Kanunu 1030
# maddelik; bu maddeler yanlis maddelere baglaniyordu.
SON_SAYI = re.compile(r"(?<!\d)(\d{1,4})\s*(?:\.|" + ORD + r")?\s*$")
AYIRAC = re.compile(r"\s*(?:,|ve|ile|ila|–|-)\s*$")
EK_ONEK = re.compile(r"(?:^|\s)(ek|geçici)\s*$", re.IGNORECASE)

# Hedef kanunu belirleyen isaretler
BU_KANUN = re.compile(r"\b[Bb]u\s+(?:Kanun|KANUN)")
SAYILI_KANUN = re.compile(r"(\d{3,4})\s*say[ıi]l[ıi]")

AD_NUMARA = {
    "türk borçlar kanunu": "6098", "borçlar kanunu": "6098",
    "türk medeni kanunu": "4721", "medeni kanun": "4721",
    "türk ceza kanunu": "5237", "ceza kanunu": "5237",
    "hukuk muhakemeleri kanunu": "6100", "türk ticaret kanunu": "6102",
    "iş kanunu": "4857", "deniz iş kanunu": "854", "basın iş kanunu": "5953",
    "sendikalar ve toplu iş sözleşmesi kanunu": "6356",
    "sosyal sigortalar ve genel sağlık sigortası kanunu": "5510",
    "iş mahkemeleri kanunu": "7036",
}
AD_RE = re.compile("|".join(re.escape(a) for a in
                            sorted(AD_NUMARA, key=len, reverse=True)), re.IGNORECASE)


def _kucult(s: str) -> str:
    """Turkce guvenli kucultme: 'İ'.lower() 'i' + birlesik nokta uretiyor."""
    return s.replace("İ", "i").replace("I", "ı").lower().replace("̇", "")


# Iliski turu ipuclari; ustteki once denenir.
ILISKI_IPUCLARI = [
    ("mulga",      r"yürürlükten kaldırıl|mülga|ilga edil"),
    ("degistirir", r"değiştiril|değişik|eklenmiştir|ibaresi|ibareleri"),
    ("istisna",    r"istisna|saklıdır|hariç|uygulanmaz|dışında|tabi değil|"
                   r"dahil değil|bu hüküm.{0,20}uygulanmaz"),
    ("yaptirim",   r"idari para cezası|para cezası|aykırı hareket|cezalandırıl|"
                   r"aykırı davran"),
    ("gonderme",   r"hükümleri uygulanır|hükümlerine göre|uyarınca|gereğince|"
                   r"hükümlerine tabi|hükmü uygulanır|belirtilen|göre"),
]
ILISKI_DERLI = [(ad, re.compile(k, re.IGNORECASE)) for ad, k in ILISKI_IPUCLARI]


# Kanit metninin ekranda kaplayacagi yer. Cumle bundan uzunsa atfin
# ETRAFINDAN pencere alinir; basindan degil.
KANIT_UZUNLUK = 200


def _cumle(metin: str, konum: int, yaricap: int = 240) -> str:
    """Atfin gectigi cumleyi doner; ATIF HER ZAMAN ICINDE OLUR.

    Onceki surum cumle basindan baslayip sabit uzunlukta kirpiyordu ve
    hukuk metninde bu sik sik atfi disarida birakiyordu: "a)", "f)" gibi
    bent isaretleri ve tarihlerdeki noktalar cumle sinirini yanlis yerde
    buluyor, uzun bir liste cumlesi cikiyor, kirpma da atfa varmadan
    bitiyordu. Ekranda "4857 sayili Kanunun 25 inci maddesi" yazmasi
    gereken yerde onun oncesindeki bent listesi gorunuyordu.

    Simdi: cumle kisa ise oldugu gibi, uzunsa atfin etrafindan pencere.
    """
    bas = metin.rfind(".", max(0, konum - yaricap), konum)
    bas = bas + 1 if bas != -1 else max(0, konum - yaricap)
    son = metin.find(".", konum)
    son = son + 1 if son != -1 else min(len(metin), konum + yaricap)
    cumle = " ".join(metin[bas:son].split())

    if len(cumle) <= KANIT_UZUNLUK:
        return cumle

    # Cumle uzun: atfi ortalayan bir pencere al. Atif ifadesi ("25 inci
    # maddesinin ...") sagda devam ettigi icin agirlik saga veriliyor.
    sol = max(bas, konum - 100)
    sag = min(son, konum + KANIT_UZUNLUK - 100)
    parca = metin[sol:sag]
    # Kelime ortasindan baslamasin
    if sol > bas and " " in parca:
        parca = parca[parca.index(" ") + 1:]
    return ("… " if sol > bas else "") + " ".join(parca.split()) +            ("…" if sag < son else "")


def _hedef_kanun(metin: str, konum: int, kendi_no: str, pencere: int = 150) -> str:
    """Atif hangi kanuna? Bulunamazsa maddenin kendi kanunu."""
    onceki = metin[max(0, konum - pencere):konum]
    adaylar = []
    for m in SAYILI_KANUN.finditer(onceki):
        adaylar.append((m.start(), m.group(1)))
    for m in BU_KANUN.finditer(onceki):
        adaylar.append((m.start(), kendi_no))
    for m in AD_RE.finditer(onceki):
        adaylar.append((m.start(), AD_NUMARA.get(_kucult(m.group(0)), kendi_no)))
    if not adaylar:
        return kendi_no          # ciplak "18 inci maddesi" = kendi kanunu
    return max(adaylar)[1]       # en yakin (en sagdaki) isaret kazanir


def _iliski(cumle: str) -> str:
    for ad, kalip in ILISKI_DERLI:
        if kalip.search(cumle):
            return ad
    return "atif"


def _geriye_sayilar(onceki: str, en_fazla: int = 10) -> list[str]:
    """Capadan geriye dogru sayi zincirini okur: '68, 69 ve 70 inci' -> [70,69,68]."""
    sayilar: list[str] = []
    kalan = onceki.rstrip()
    while len(sayilar) < en_fazla:
        m = SON_SAYI.search(kalan)
        if not m:
            break
        kalan = kalan[:m.start()]
        onek = "Geçici " if (e := EK_ONEK.search(kalan)) and \
                            _kucult(e.group(1)) == "geçici" else \
               ("Ek " if e else "")
        sayilar.append(onek + m.group(1))
        if onek:
            break                       # "ek 2 nci madde" zinciri burada biter
        a = AYIRAC.search(kalan)
        if not a:
            break
        kalan = kalan[:a.start()]
    return sayilar


def maddeden_atiflar(kayit: dict) -> list[dict]:
    metin = kayit.get("metin") or ""
    kendi_no = str(kayit.get("mevzuat_no"))
    kendi_madde = str(kayit.get("madde_no"))
    kenarlar: list[dict] = []
    gorulen: set[tuple[str, str, str]] = set()

    for m in MADDE_KEL.finditer(metin):
        onceki = metin[max(0, m.start() - 90):m.start()]
        sayilar = _geriye_sayilar(onceki)
        if not sayilar:
            continue
        hedef_kanun = _hedef_kanun(metin, m.start(), kendi_no)
        c = _cumle(metin, m.start())
        iliski = _iliski(c)
        for no in sayilar:
            if hedef_kanun == kendi_no and no == kendi_madde:
                continue                # kendi kendine atif
            anahtar = (hedef_kanun, no, iliski)
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            kenarlar.append({
                "kaynak": f"{kendi_no}-{kendi_madde}",
                "hedef": f"{hedef_kanun}-{no}",
                "iliski": iliski,
                "kanit": c,
            })
    return kenarlar


GRAF_YOLU_ADI = "atif_grafi.json"


def grafi_kur(kayitlar: list[dict]) -> dict:
    """Kulliyattan ileri ve geri atif dizinlerini kurar.

    ileri: "{kanun}-{madde}" -> [{hedef, iliski, kanit}]
    geri : "{kanun}-{madde}" -> ["{kanun}-{madde}", ...]

    Geri dizin ayri tutuluyor cunku avukat iki yonu de soruyor: "bu madde
    nereye bagli" ve "buna kim atif yapiyor".
    """
    ileri: dict[str, list[dict]] = {}
    geri: dict[str, list[str]] = {}
    for k in kayitlar:
        for e in maddeden_atiflar(k):
            ileri.setdefault(e["kaynak"], []).append(
                {"hedef": e["hedef"], "iliski": e["iliski"], "kanit": e["kanit"]})
            hedefe = geri.setdefault(e["hedef"], [])
            if e["kaynak"] not in hedefe:
                hedefe.append(e["kaynak"])
    return {"ileri": ileri, "geri": geri}


def kaydet(graf: dict, yol=None) -> None:
    import config

    yol = yol or (config.INDEX_DIR / GRAF_YOLU_ADI)
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    with gecici.open("w", encoding="utf-8") as f:
        json.dump(graf, f, ensure_ascii=False)
    import os
    os.replace(gecici, yol)


class AtifGrafi:
    """Kurulmus grafi okuyup madde bazinda sorgular.

    Graf yoksa hazir_mi() False doner ve site grafsiz calismaya devam eder;
    bu bir ek, onkosul degil.
    """

    def __init__(self, yol=None):
        import config

        self.yol = yol or (config.INDEX_DIR / GRAF_YOLU_ADI)
        self._graf: dict | None = None

    def _yukle(self) -> dict:
        if self._graf is None:
            try:
                self._graf = json.loads(self.yol.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._graf = {"ileri": {}, "geri": {}}
        return self._graf

    def hazir_mi(self) -> bool:
        return bool(self._yukle().get("ileri"))

    def sayi(self) -> int:
        return sum(len(v) for v in self._yukle().get("ileri", {}).values())

    def atiflar(self, mevzuat_no: str, madde_no: str) -> list[dict]:
        """Bu maddenin YAPTIGI atiflar."""
        return self._yukle().get("ileri", {}).get(f"{mevzuat_no}-{madde_no}", [])

    def atif_yapanlar(self, mevzuat_no: str, madde_no: str) -> list[str]:
        """Bu maddeye atif YAPAN maddeler."""
        return self._yukle().get("geri", {}).get(f"{mevzuat_no}-{madde_no}", [])
