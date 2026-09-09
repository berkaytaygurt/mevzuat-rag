"""Buronun kendi belgelerinde arama: indeksleme ve sorgulama.

NEDEN AYRI BIR MODUL

Kanun maddesi aramakla kendi dilekcesini aramak ayni is degil:

  MEVZUAT  : birim dogal olarak belli (madde), kullanici "hangi madde"
             diye soruyor, cevap TEK BIR PARCA.
  ARSIV    : birim BELGE, kullanici "hangi dosyamda bundan bahsetmisim"
             diye soruyor. Eslesme parca duzeyinde olur ama cevap
             belge olmali; yoksa ayni dosyanin dort parcasi ilk dort
             sirayi kapatir ve liste tek dosyadan ibaret gorunur.

UC TASARIM KARARI

1. BOLUM FARKINDA PARCALAMA. Dilekce sabit bir duzeni var (TARAFLAR,
   KONU, ACIKLAMALAR, HUKUKI SEBEPLER, SONUC). Sabit pencereyle
   bolmek bir argumani ikiye ayirabiliyor; basliklardan boluyoruz.

2. KALIP BOLUMLER ELENIYOR. Her dilekcede ayni cumleler var:
   "Yukarida arz ve izah edilen nedenlerle...", "her turlu yasal
   delil". Bunlar indekslenirse butun belgeler birbirine benzer ve
   arama ayirt edemez. Kalip agirlikli bolumler (DELILLER, SONUC VE
   ISTEM) indeks disi.

3. BELGE DUZEYINDE TOPLAMA. Bir belgenin puani, EN IYI parcasinin
   puani (maksimum). Toplam almak uzun belgeleri kayiriyor: on
   parcali bir dilekce, konuyla tek cumlede ilgilense bile ortalamayi
   yukseltip one gecebiliyor.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np

import config

log = logging.getLogger(__name__)

# Dilekce bolum basliklari. Buyuk harfli ve iki nokta ya da satir sonu
# ile biterler.
# Bolum basliklari. IKI BICIM de taninmali:
#
#   KONU : Sunun sundan iptali talebidir.     <-- icerik AYNI SATIRDA
#   ACIKLAMALAR                                <-- baslik yalniz
#
# Ilk surum yalnizca ikinciyi taniyordu ("...\s*$"). Gercek dilekce
# formati birincisi oldugu icin KONU satiri hic bulunamadi -- yani
# dilekcenin KENDI OZETI indekse girmedi -- ve TARAF bolumleri de
# ayiklanamadigi icin isim/adres indekse SIZDI. Iki hata tek satirdan.
BOLUM_RE = re.compile(
    r"^[ 	]*(TARAFLAR|DAVACI|DAVALI|VEKİLİ|VEKILI|MÜŞTEKİ|MUSTEKI|"
    r"ŞÜPHELİ|SUPHELI|SANIK|ŞİKAYETÇİ|SIKAYETCI|MAĞDUR|MAGDUR|KONU|"
    r"AÇIKLAMALAR|ACIKLAMALAR|OLAYLAR|"
    r"HUKUKİ SEBEPLER|HUKUKI SEBEPLER|HUKUKİ NEDENLER|HUKUKI NEDENLER|"
    r"DELİLLER|DELILLER|SONUÇ VE İSTEM|SONUC VE ISTEM|NETİCE|NETICE|"
    r"TALEP|ADRES|TELEFON)[ 	]*(?:[:：]|$)",
    re.MULTILINE)

# Bu bolumler neredeyse tamamen kalip. Icerik tasimadiklari icin
# indekslenmiyorlar.
KALIP_BOLUMLER = {
    "DELİLLER", "DELILLER", "SONUÇ VE İSTEM", "SONUC VE ISTEM",
    "NETİCE", "NETICE", "TALEP",
}
# Taraf bilgisi de aranmiyor: isim ve adres, "hangi konuda yazmistim"
# sorusunun cevabi degil. Ayrica kisisel veri.
TARAF_BOLUMLERI = {
    "TARAFLAR", "DAVACI", "DAVALI", "VEKİLİ", "VEKILI",
    "MÜŞTEKİ", "MUSTEKI", "ŞÜPHELİ", "SUPHELI", "SANIK",
    "ŞİKAYETÇİ", "SIKAYETCI", "MAĞDUR", "MAGDUR", "ADRES", "TELEFON",
}

EN_AZ_PARCA = 120          # bundan kisa parca aramaya bir sey katmiyor
EN_COK_PARCA = 1400        # gomme modelinin penceresini zorlamamak icin


def bolumlere_ayir(metin: str) -> list[tuple[str, str]]:
    """Dilekceyi (baslik, govde) ciftlerine ayirir.

    Baslik bulunamazsa tek bir parca doner; bicimi taninmayan belgeler
    (bilirkisi raporu, e-posta) de calismaya devam etsin diye.
    """
    isaretler = list(BOLUM_RE.finditer(metin))
    if not isaretler:
        return [("", metin.strip())]
    bolumler = []
    bas = isaretler[0].start()
    if bas > 0 and metin[:bas].strip():
        bolumler.append(("", metin[:bas].strip()))
    for i, m in enumerate(isaretler):
        son = isaretler[i + 1].start() if i + 1 < len(isaretler) else len(metin)
        baslik = m.group(1).upper()
        govde = metin[m.end():son].strip()
        if govde:
            bolumler.append((baslik, govde))
    return bolumler


def _uzun_bolumu_bol(govde: str) -> list[str]:
    """Uzun bolumu numarali paragraflardan boler.

    ACIKLAMALAR bolumu genelde "1. ... 2. ..." diye gidiyor ve her
    numara ayri bir olgu. Sabit karakter penceresi bir olgunun
    ortasindan kesebiliyordu.
    """
    if len(govde) <= EN_COK_PARCA:
        return [govde]
    parcalar, simdiki = [], ""
    for paragraf in re.split(r"\n\s*(?=\d+[.)]\s)", govde):
        if len(simdiki) + len(paragraf) > EN_COK_PARCA and simdiki:
            parcalar.append(simdiki.strip())
            simdiki = paragraf
        else:
            simdiki += ("\n" if simdiki else "") + paragraf
    if simdiki.strip():
        parcalar.append(simdiki.strip())
    return parcalar


# KONU satiri, dilekcenin KENDI OZETI -- avukatin "bu dilekce ne
# hakkinda" diye yazdigi tek cumle. Olculdu: bu satir elenince arama
# butun sonuclari uzun ACIKLAMALAR bolumlerinden getiriyordu ve
# "kandirip parasini almislar" gibi gunluk dille yazilmis bir sorgu
# "nitelikli dolandiricilik" diyen dilekceyi hic bulamiyordu.
#
# Iki duzeltme: (1) KONU uzunluk esigine takilmiyor, (2) puani
# agirliklandiriliyor. Belge puani EN IYI parcasinin puani oldugu icin
# agirlik, KONU eslesmesini anlati eslesmesinin onune geciriyor.
OZET_BOLUMLERI = {"KONU"}
# Kisa ama degerli bolumler: uzunluk esigine takilmasinlar.
KISA_AMA_DEGERLI = {"KONU", "HUKUKİ SEBEPLER", "HUKUKI SEBEPLER",
                    "HUKUKİ NEDENLER", "HUKUKI NEDENLER"}
# OLCULDU: agirlik 1.6 ve 1.15 denendi, IKISI DE ZARAR VERDI
# (MRR 0.791 -> 0.603 ve 0.674). Sebep: RRF puanlari cok kucuk
# (1/(60+sira)) ve carpan, 40. siradaki zayif bir KONU eslesmesini
# 5. siradaki guclu bir ACIKLAMALAR eslesmesinin ustune cikariyor.
# KONU'yu INDEKSE ALMAK kazandiriyor, one CIKARMAK degil.
OZET_AGIRLIGI = 1.0


def parcala(metin: str, belge_adi: str) -> list[dict]:
    """Belgeyi aranabilir parcalara ayirir."""
    parcalar = []
    for baslik, govde in bolumlere_ayir(metin):
        if baslik in KALIP_BOLUMLER or baslik in TARAF_BOLUMLERI:
            continue
        ozet = baslik in OZET_BOLUMLERI
        kisa_gecerli = baslik in KISA_AMA_DEGERLI
        for i, parca in enumerate(_uzun_bolumu_bol(govde)):
            if len(parca) < EN_AZ_PARCA and not kisa_gecerli:
                continue
            # Baslik metne katiliyor: "HUKUKI SEBEPLER" bolumundeki bir
            # kanun listesi, baslik olmadan baglamsiz kaliyor.
            tam = f"{baslik}: {parca}" if baslik else parca
            parcalar.append({
                "belge": belge_adi,
                "bolum": baslik,
                "sira": i,
                "agirlik": OZET_AGIRLIGI if ozet else 1.0,
                "metin": tam[:EN_COK_PARCA],
            })
    return parcalar


# Arsiv sorgusundaki DOLGU. Avukat "hani bir dilekcemiz vardi, kiraci
# odemiyordu ya" diye yaziyor. Buradaki kelimelerin cogu konu tasimiyor:
#
#   - "dilekce", "dosya", "dava" : HER belge zaten bunlardan biri.
#     BM25 bunu IDF ile kendiliginden soneyimliyor ama GOMME MODELI
#     soneyimlemiyor -- sorgu vektoru "dilekce"ye dogru kayiyor ve
#     butun belgelere esit yakin duruyor.
#   - "hani, su, o, ya, falan, iste" : hicbir sey.
#   - "vardi, istemistik, etmislerdi" : anlati zamani, konu degil.
#
# retrieve.cekirdek_sorgu bu isi yapmiyor: o SORU kaliplarini
# ("ne kadar", "hangi", "midir") atmak icin yazilmis ve arsiv
# sorgusunda hicbirine rastlamiyor.
# Desen yerine KELIME LISTESI kullaniliyor. Ilk surum regex sinirlariyla
# yazildi ve sinirlar kaynak dosyaya hic ulasmadi -- desen sessizce
# hicbir seyi eslemedi, sadelestirme calisiyor gorunup calismiyordu.
# Kelime bolup listeye bakmak hem o tuzaga bagisik hem Turkce'de daha
# dogru calisiyor.
DOLGU = {
    "hani", "su", "o", "bir", "ya", "falan", "filan", "iste",
    "sey", "yani", "hic", "onu", "bunu",
    "şu", "işte", "şey", "hiç",
    # Her belge zaten bir dilekce/dosya/dava. BM25 bunu IDF ile
    # soneyimliyor ama GOMME MODELI soneyimlemiyor: sorgu vektoru
    # "dilekce"ye kayiyor ve butun belgelere esit yakin duruyor.
    "dilekçe", "dilekce", "dilekçemiz", "dilekçesi", "dilekçeyi",
    "dosya", "dosyası", "dosyamız", "dava", "davası",
    # Anlati zamani; konu tasimiyor.
    "vardı", "vardır", "istemiştik", "istiyordu", "istiyorduk",
    "olmuştu", "etmişlerdi", "yapmışlardı", "etmiştik",
    "bulabilir", "bulabilirim", "arıyorum", "hatırlıyorum",
    "geçen", "önceki", "eski", "müvekkil", "müvekkili",
}

# Temizlikten sonra bundan az kelime kalirsa dolgu degil ICERIK
# atmisiz demektir; o zaman asil sorgu kullaniliyor.
EN_AZ_KELIME = 2


def sorguyu_sadelestir(soru: str) -> str:
    """Arsiv sorgusundan dolguyu atar; guvenli degilse sorguyu aynen doner."""
    kelimeler = re.findall(chr(92) + "w+", soru or "")
    kalan = [k for k in kelimeler if k.lower() not in DOLGU]
    if len(kalan) < EN_AZ_KELIME:
        return soru
    return " ".join(kalan)


ALINTI_UZUNLUK = 420


def alinti_sec(metin: str, soru: str, uzunluk: int = ALINTI_UZUNLUK) -> str:
    """Parcanin ESLESEN yerinden bir pencere doner.

    Once parcanin ilk 420 karakteri veriliyordu ve avukat cogu zaman
    aradigi cumleyi GORMUYORDU: eslesme 1400 karakterlik bir bolumun
    sonundaysa ekranda olayin girisi ("Davali sirket bunyesinde...")
    cikiyor, "savunmasi alinmadan" cumlesi gorunmuyordu. Alintinin tek
    isi tanitmak; yanlis yeri gostermesi onu isesiz birakiyor.

    Yontem basit ve yerel: sorgu koklerinin en yogun gectigi yeri bulup
    cevresini kesiyoruz.
    """
    if not metin:
        return ""
    if len(metin) <= uzunluk:
        return metin

    kokler = [k[:5].lower() for k in re.findall(r"\w+", soru or "")
              if len(k) > 3]
    if not kokler:
        return metin[:uzunluk]

    dusuk = metin.lower()
    yerler = []
    for kok in set(kokler):
        bas = dusuk.find(kok)
        while bas != -1:
            yerler.append(bas)
            bas = dusuk.find(kok, bas + 1)
    if not yerler:
        return metin[:uzunluk]

    # Kayan pencere: icinde en cok eslesme olan baslangici sec.
    yerler.sort()
    en_iyi_bas, en_iyi_sayi = yerler[0], 0
    for y in yerler:
        sayi = sum(1 for x in yerler if y <= x < y + uzunluk)
        if sayi > en_iyi_sayi:
            en_iyi_bas, en_iyi_sayi = y, sayi

    # Pencereyi eslesmenin biraz oncesinden baslat ki baglam kalsin.
    bas = max(0, en_iyi_bas - 90)
    # Kelime ortasindan kesme
    if bas > 0:
        bosluk = metin.find(" ", bas)
        bas = bosluk + 1 if 0 <= bosluk < bas + 40 else bas
    parca = metin[bas:bas + uzunluk].strip()
    return ("… " if bas > 0 else "") + parca


class Arsiv:
    """Belge kulliyatini indeksler ve arar."""

    def __init__(self, embedder, dizin: Path | None = None):
        self.embedder = embedder
        self.dizin = Path(dizin or (config.ROOT / "data" / "arsiv_indeks"))
        self._parcalar: list[dict] = []
        self._vektorler: np.ndarray | None = None
        self._bm25 = None
        self._bm25_belirtec: list[list[str]] = []
        self._belirtecle = None

    # ---------- indeksleme ----------
    def indeksle(self, belgeler: dict[str, str], goster: bool = True) -> int:
        """belgeler: {belge_adi: metin}. Butun indeksi yeniden kurar."""
        parcalar: list[dict] = []
        for ad, metin in belgeler.items():
            parcalar.extend(parcala(metin, ad))
        if not parcalar:
            raise ValueError("indekslenecek parca cikmadi")

        vektorler = self.embedder.encode_documents(
            [p["metin"] for p in parcalar], goster=goster)
        self._parcalar = parcalar
        self._vektorler = np.asarray(vektorler, dtype=np.float32)
        self._bm25 = None
        self.dizin.mkdir(parents=True, exist_ok=True)
        np.save(self.dizin / "vektorler.npy", self._vektorler)
        (self.dizin / "parcalar.json").write_text(
            json.dumps(parcalar, ensure_ascii=False), encoding="utf-8")
        log.info("arsiv indekslendi: %d belge, %d parca",
                 len(belgeler), len(parcalar))
        return len(parcalar)

    def yukle(self) -> None:
        self._vektorler = np.load(self.dizin / "vektorler.npy")
        self._parcalar = json.loads(
            (self.dizin / "parcalar.json").read_text("utf-8"))

    # ---------- BM25 ----------
    def _bm25_kur(self) -> None:
        from rank_bm25 import BM25Okapi

        from core.retrieve import Retriever

        # Mevzuat tarafiyla AYNI belirtecleyici: Turkce katlama orada
        # ("kisisel" ile "kişisel" ayni belirtec) ve burada farkli bir
        # bolme kullanmak sessizce daha kotu eslesme demek olurdu.
        self._belirtecle = Retriever._tokenize
        self._bm25_belirtec = [self._belirtecle(p["metin"]) for p in self._parcalar]
        self._bm25 = BM25Okapi(self._bm25_belirtec)

    # ---------- arama ----------
    def ara(self, soru: str, limit: int = 10, aday: int = 40,
            sadelestir: bool = True) -> list[dict]:
        """Belge duzeyinde sonuc doner (parca degil).

        Vektor ve BM25 siralamalari RRF ile birlestiriliyor; mevzuat
        tarafinda olculup ise yaradigi gorulen yontem burada da
        kullaniliyor.
        """
        if self._vektorler is None:
            self.yukle()
        if self._bm25 is None:
            self._bm25_kur()

        if sadelestir:
            soru = sorguyu_sadelestir(soru)
        sorgu = np.asarray(self.embedder.encode_query(soru),
                           dtype=np.float32).reshape(-1)
        benzerlik = self._vektorler @ sorgu
        vektor_sira = np.argsort(-benzerlik)[:aday]

        bm_puan = self._bm25.get_scores(self._belirtecle(soru))
        bm_sira = np.argsort(-bm_puan)[:aday]

        # RRF: sira sayisinin tersi toplaniyor, ham puanlar degil.
        # Iki yontemin puan olcekleri karsilastirilamaz.
        K = 60
        puanlar: dict[int, float] = {}
        for r, i in enumerate(vektor_sira):
            puanlar[int(i)] = puanlar.get(int(i), 0.0) + 1.0 / (K + r)
        for r, i in enumerate(bm_sira):
            puanlar[int(i)] = puanlar.get(int(i), 0.0) + 1.0 / (K + r)

        # Belge duzeyinde topla: EN IYI parca belgeyi temsil ediyor.
        belgeler: dict[str, dict] = {}
        for i, puan in puanlar.items():
            p = self._parcalar[i]
            puan *= p.get("agirlik", 1.0)
            mevcut = belgeler.get(p["belge"])
            if mevcut is None or puan > mevcut["puan"]:
                belgeler[p["belge"]] = {
                    "belge": p["belge"], "puan": puan,
                    "bolum": p["bolum"],
                    # Avukat alintiyi okuyup dosyayi TANIYACAK; hem
                    # yeterince uzun hem ESLESEN yerden olmali.
                    "alinti": alinti_sec(p["metin"], soru),
                    "vektor_benzerlik": float(benzerlik[i]),
                }
        return sorted(belgeler.values(), key=lambda x: -x["puan"])[:limit]
