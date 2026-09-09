"""Belgedeki dogrudan tanimlayicilari yer tutucuya cevirir, sonra geri koyar.

NEDEN

Avukat bir dilekce yukleyecek. Dilekcede muvekkilin adi, TC kimlik
numarasi, adresi, IBAN'i var. Bu veri avukatin degil MUVEKKILIN verisi
ve o kisi Google'a gitmesine riza vermedi. Avukatlik Kanunu m.36 sir
saklama yukumlulugu getiriyor, KVKK'da avukat veri sorumlusu.

Bu modul metni Gemini'ye gondermeden ONCE yerelde temizler; donen
cevapta yer tutuculari yerine koyar. Esleme tablosu yalnizca bellekte,
kullanicinin makinesinde kalir -- diske yazilmaz, disari gonderilmez.

NE OLDUGUNU DOGRU ADLANDIRMAK

Bu ANONIMLESTIRME DEGIL, TAKMA ADLASTIRMA. Isim silinse bile olgular
kimligi geri verebiliyor: "8 yil calismis, X sirketinde performans
gerekcesiyle cikarilmis, 2019'da is kazasi gecirmis kisi" tarifi tek
bir kisiyi isaret eder. KVKK bakimindan takma adlastirilmis veri HALA
kisisel veridir. Bu modul riski ciddi olcude azaltir ama "artik kisisel
veri degil" demez; kullaniciya da boyle sunulmamali.

TASARIM

Dogrudan tanimlayicilar iki gruba ayriliyor:

  DOGRULANABILIR : TC kimlik no ve IBAN'in kendi saglama hanesi var.
                   Desene benzeyen her sey degil, MATEMATIKSEL OLARAK
                   gecerli olanlar maskeleniyor. Yanlis pozitif ~sifir.
  DESENE DAYALI  : e-posta, telefon, plaka. Bicimleri yeterince ozel.

Isimler ayri bir sorun ve burada COZULMUYOR: Turkce isimlerin deseni
yok, buyuk harf sezgisi de hukuk metninde cokuyor ("Is Kanunu",
"Yargitay 9. Hukuk Dairesi", "Turk Borclar Kanunu" hepsi buyuk harfli
ve maskelenirse analiz bozulur). Isim tespiti `isim.py`de sozluk ve
kullanici onayiyla yapiliyor; burasi yalnizca makinenin kesin
bilebildigi seyleri alir.
"""
from __future__ import annotations

import re

# Yer tutucu bicimi. Koseli parantez secildi cunku Gemini bunu metin
# icinde bozmadan tasiyor ve kanun metninde kosesli parantez az geciyor.
KALIP = "[{tur}_{no}]"

EPOSTA_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
# Turkiye telefon: +90 555 123 45 67 / 0555 123 45 67 / 5551234567
TELEFON_RE = re.compile(
    r"(?<!\d)(?:\+?90[\s.-]?)?(?:0[\s.-]?)?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)")
# Plaka: 34 ABC 123 / 06 AB 1234
PLAKA_RE = re.compile(r"\b(0[1-9]|[1-7]\d|8[01])\s?[A-ZÇĞİÖŞÜ]{1,3}\s?\d{2,4}\b")
IBAN_RE = re.compile(r"\bTR\s?(?:\d{2}\s?)(?:\d{4}\s?){5}\d{2}\b", re.IGNORECASE)
ONBIR_HANE_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")


def tc_gecerli(no: str) -> bool:
    """TC kimlik numarasinin saglama hanelerini dogrular.

    11 haneyi desenle yakalamak yetmez: dosya numarasi, tarih dizisi ya
    da tutar da 11 hane olabilir. Saglama sayesinde "11 rakam gordum"
    degil "bu gercekten bir TC kimlik numarasi" diyebiliyoruz.
    """
    if len(no) != 11 or not no.isdigit() or no[0] == "0":
        return False
    h = [int(c) for c in no]
    tek = h[0] + h[2] + h[4] + h[6] + h[8]      # 1., 3., 5., 7., 9.
    cift = h[1] + h[3] + h[5] + h[7]            # 2., 4., 6., 8.
    if (tek * 7 - cift) % 10 != h[9]:
        return False
    return sum(h[:10]) % 10 == h[10]


def iban_gecerli(iban: str) -> bool:
    """IBAN'i mod-97 kuralina gore dogrular (ISO 13616)."""
    s = re.sub(r"\s", "", iban).upper()
    if len(s) != 26 or not s.startswith("TR"):
        return False
    tasinmis = s[4:] + s[:4]
    sayi = "".join(str(ord(c) - 55) if c.isalpha() else c for c in tasinmis)
    return int(sayi) % 97 == 1


class Maske:
    """Metni maskeler ve geri koyar. Tablo yalnizca bu nesnede yasar."""

    def __init__(self) -> None:
        self.tablo: dict[str, str] = {}     # yer tutucu -> asil deger
        self._ters: dict[str, str] = {}     # asil deger -> yer tutucu
        self._sayac: dict[str, int] = {}

    def _yer_tutucu(self, tur: str, deger: str) -> str:
        """Ayni deger her yerde AYNI yer tutucuyu alir.

        Onemli: "Ahmet Yilmaz" belgede 40 kez gecerse 40'i da [KISI_1]
        olmali. Farkli numara verilirse model tek kisiyi birden fazla
        taraf saniyor ve analiz tarafları karistiriyor.
        """
        anahtar = re.sub(r"\s+", " ", deger.strip())
        if anahtar in self._ters:
            return self._ters[anahtar]
        self._sayac[tur] = self._sayac.get(tur, 0) + 1
        yt = KALIP.format(tur=tur, no=self._sayac[tur])
        self.tablo[yt] = anahtar
        self._ters[anahtar] = yt
        return yt

    def maskele(self, metin: str) -> str:
        """Dogrudan tanimlayicilari yer tutucuyla degistirir."""
        if not metin:
            return metin

        def degistir(eslesme, tur):
            return self._yer_tutucu(tur, eslesme.group(0))

        # SIRA ONEMLI: IBAN icinde 11 haneli dizi bulunabilir, once IBAN.
        metin = IBAN_RE.sub(
            lambda m: degistir(m, "IBAN") if iban_gecerli(m.group(0))
            else m.group(0), metin)
        metin = EPOSTA_RE.sub(lambda m: degistir(m, "EPOSTA"), metin)
        # TC yalnizca saglama tutuyorsa maskeleniyor.
        metin = ONBIR_HANE_RE.sub(
            lambda m: degistir(m, "TCKN") if tc_gecerli(m.group(0))
            else m.group(0), metin)
        metin = TELEFON_RE.sub(lambda m: degistir(m, "TEL"), metin)
        metin = PLAKA_RE.sub(lambda m: degistir(m, "PLAKA"), metin)
        return metin

    def ekle(self, deger: str, tur: str = "KISI") -> str:
        """Kullanicinin elle isaretledigi degeri maskeye dahil eder.

        Isim tespiti makineye birakilamadigi icin (bkz. modul aciklamasi)
        avukat gonderilecek metni gorup eksik kalani isaretliyor.
        """
        return self._yer_tutucu(tur, deger)

    def maskele_degerler(self, metin: str) -> str:
        """Elle eklenen degerleri metinde arayip degistirir.

        Duz str.replace YETMIYOR: tablodaki deger bosluklari tek bosluga
        indirilmis halde tutuluyor, oysa PDF metninde ayni ad satir sonu
        ya da cift bosluk tasiyabiliyor ("Ahmet\\nYılmaz"). Eslesme
        bulunamayinca isim sessizce maskelenmeden disari giderdi.
        Bu yuzden bosluklara toleransli desenle araniyor.
        """
        for asil, yt in sorted(self._ters.items(), key=lambda x: -len(x[0])):
            desen = r"\s+".join(re.escape(p) for p in asil.split(" ") if p)
            if not desen:
                continue
            metin = re.sub(desen, yt.replace("\\", "\\\\"), metin)
        return metin

    def geri_koy(self, metin: str) -> str:
        """Yer tutuculari asil degerleriyle degistirir.

        Cevap Gemini'den yer tutucularla geliyor; kullaniciya
        gostermeden once burada yerelde geri konuyor.
        """
        for yt, asil in self.tablo.items():
            metin = metin.replace(yt, asil)
        return metin

    def ozet(self) -> dict[str, int]:
        """Hangi turden kac tanimlayici maskelendi."""
        sayi: dict[str, int] = {}
        for yt in self.tablo:
            tur = yt.strip("[]").rsplit("_", 1)[0]
            sayi[tur] = sayi.get(tur, 0) + 1
        return sayi
