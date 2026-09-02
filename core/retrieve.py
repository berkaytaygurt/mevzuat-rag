"""Hibrit arama: vektor + BM25 + dogrudan madde numarasi eslesmesi.

Neden tek basina vektor yetmiyor: kullanici "TBK 6. madde ne diyor" diye sorar.
Anlamsal benzerlik sayi eslestirmede zayiftir; "6" ile "60" arasindaki farki
kaciran bir cevap hukuki olarak tamamen yanlistir. Bu yuzden uc yol birlikte
calisir ve sonuclar RRF ile birlestirilir.
"""
from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path

import config
from .store import MevzuatStore

log = logging.getLogger(__name__)

# "TBK 6", "4857 sayili kanun madde 53", "IS KANUNU m. 25", "madde 18"
MADDE_REF_RE = re.compile(
    r"(?:madde|m\.|mad\.)\s*(\d+)|(\d+)\s*(?:\.|inci|nci|uncu|üncü|ıncı)?\s*madde",
    re.IGNORECASE)
KANUN_NO_RE = re.compile(r"\b(\d{4})\s*(?:sayılı|sayili)\b", re.IGNORECASE)

# Yaygin kisaltmalar -> kanun numarasi
KISALTMALAR = {
    "tbk": "6098", "tmk": "4721", "tck": "5237", "hmk": "6100",
    "ttk": "6102", "cmk": "5271", "ik": "4857", "iyuk": "2577",
    "vuk": "213", "kvkk": "6698", "ikk": "6331",
}

# Turkce harf -> ASCII karsiligi
_TR_HARITA = str.maketrans({
    "ş": "s", "Ş": "s", "ı": "i", "I": "i", "İ": "i", "i": "i",
    "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c", "â": "a", "Â": "a", "î": "i", "Î": "i",
    "û": "u", "Û": "u",
})


def _tr_katla(metin: str) -> str:
    """Turkce harfleri ASCII'ye katlar ve kucultur.

    Kullanicilar sorgularini cogunlukla Turkce karakter kullanmadan yazar
    ("kisisel veri"). Katlama olmadan BM25 "kisisel" ile "kisisel"i (s vs s)
    eslestiremiyor ve birebir baslik eslesmesi olan madde hic getirilemiyordu.
    Indeks ve sorgu tarafinda ayni katlama uygulanmali.
    """
    return metin.translate(_TR_HARITA).lower()


# Soru kaliplari. Kullanicinin sorusu ile kanun metninin dili arasindaki
# fark olculdu: kidem tazminatinin sartlarini duzenleyen madde
#
#   "kidem tazminati sartlari"                              ->  1. sira
#   "kidem tazminati"                                       ->  8. sira
#   "kidem tazminatina hak kazanmak icin ne kadar calismak
#    gerekir"                                               -> 21. sira
#
# Aradaki fark soru kelimeleri: kanun metninde "ne kadar", "gerekir mi",
# "nasil" gecmiyor, bu kelimeler vektoru konudan uzaklastiriyor. Sorgunun
# bir de bu kelimelerden arindirilmis hali aratilip iki sonuc birlestirilir.
SORU_KALIPLARI = re.compile(
    r"\b(ne\s+kadar|ne\s+zaman|nasil|nasıl|neden|nicin|niçin|hangi|"
    r"kac|kaç|kim|kimler|nedir|nelerdir|midir|mıdır|mudur|müdür|"
    r"miyim|miyiz|misin|misiniz|muyum|muyuz|musun|musunuz|"
    r"müyüm|müyüz|mıyım|mıyız|"
    r"var\s*mi|var\s*mı|olur\s*mu|gerekir\s*mi|gerekir|gerekiyor|"
    r"mi|mı|mu|mü)\b",
    re.IGNORECASE)


def cekirdek_sorgu(soru: str) -> str:
    """Sorudan soru kaliplarini atip konu cekirdegini birakir.

    Cekirdek sorgudan bir sey kalmazsa ya da cok kisalirsa bos doner;
    cagiran taraf o zaman yalnizca asil sorguyu kullanir.
    """
    # Once yalnizca noktalamayi at. Cekirdegi bununla karsilastiracagiz:
    # tek basina soru isareti silmek yeni bir arama yapmayi hak etmiyor,
    # cunku ikinci sorgu birincinin neredeyse aynisi oluyor ve RRF'e bilgi
    # yerine gurultu ekliyor. Olculdu: bu ayrim yapilmadiginda cekirdek
    # sentetik sorularin %100'unde devreye giriyordu.
    temiz = re.sub(r"[?!.]+", " ", soru)
    temiz = re.sub(r"\s+", " ", temiz).strip()

    cekirdek = SORU_KALIPLARI.sub(" ", temiz)
    cekirdek = re.sub(r"\s+", " ", cekirdek).strip()

    # Soru kelimesi atilmadiysa ikinci aramanin anlami yok
    if cekirdek.lower() == temiz.lower():
        return ""
    # Cok kisaldiysa bilgi kaybi var demektir
    if len(cekirdek) < 8:
        return ""
    return cekirdek


class Retriever:
    def __init__(self, store: MevzuatStore, embedder, bm25_yol: Path | None = None,
                 rerank: bool | None = None):
        self.store = store
        self.embedder = embedder
        self.bm25_yol = bm25_yol or (config.INDEX_DIR / "bm25.pkl")
        self.rerank = config.RERANK if rerank is None else rerank
        self._bm25 = None
        self._bm25_kayitlar: list[dict] = []
        self._reranker = None
        self._yazim = None
        self._genisletici = None
        self.son_genisletme: str | None = None
        self.son_vektor_puani: float = 0.0
        self._ham_puan_sabit: float = 0.0

    @property
    def genisletici(self):
        if self._genisletici is None:
            from .sorgu import SorguGenisletici

            self._genisletici = SorguGenisletici()
        return self._genisletici

    @property
    def yazim(self):
        if self._yazim is None:
            from .yazim import YazimDuzeltici

            self._yazim = YazimDuzeltici()
        return self._yazim

    @property
    def reranker(self):
        if self._reranker is None:
            from .reranker import Reranker

            self._reranker = Reranker()
        return self._reranker

    # ---------- BM25 ----------
    def bm25_kur(self) -> None:
        """Depodaki tum maddeler uzerinde BM25 indeksi kurar ve diske yazar."""
        from rank_bm25 import BM25Okapi

        kayitlar = self.store.tum_kayitlar()
        if not kayitlar:
            log.warning("depo bos, BM25 kurulmadi")
            return
        tokenlar = [self._tokenize(self._kayit_metni(k)) for k in kayitlar]
        bm25 = BM25Okapi(tokenlar)
        self.bm25_yol.parent.mkdir(parents=True, exist_ok=True)
        with open(self.bm25_yol, "wb") as f:
            pickle.dump({"bm25": bm25, "kayitlar": kayitlar}, f)
        self._bm25, self._bm25_kayitlar = bm25, kayitlar
        log.info("BM25 indeksi kuruldu: %d madde", len(kayitlar))

    @property
    def bm25(self):
        if self._bm25 is None and self.bm25_yol.exists():
            with open(self.bm25_yol, "rb") as f:
                d = pickle.load(f)
            self._bm25, self._bm25_kayitlar = d["bm25"], d["kayitlar"]
        return self._bm25

    @staticmethod
    def _kayit_metni(k: dict) -> str:
        """BM25'e verilecek metin. Baslik uc kez tekrarlanir.

        Madde basligi, maddenin ne hakkinda oldugunu en yogun anlatan alandir
        ("Kisisel verilerin islenme sartlari"). Tekrar etmeden, uzun govde
        metni basligi seyreltiyor ve birebir baslik eslesmesi ust siraya
        cikamiyordu.
        """
        baslik = k.get("baslik", "")
        return " ".join(filter(None, [
            k.get("mevzuat_adi", ""),
            baslik, baslik, baslik,
            f"madde {k.get('madde_no','')}",
            k.get("metin", ""),
        ]))

    @staticmethod
    def _tokenize(metin: str) -> list[str]:
        return re.findall(r"\w+", _tr_katla(metin))

    # ---------- madde numarasi ----------
    def _dogrudan_madde(self, soru: str, limit: int = 3) -> list[dict]:
        m = MADDE_REF_RE.search(soru)
        if not m:
            return []
        madde_no = m.group(1) or m.group(2)

        kanun_no = None
        if km := KANUN_NO_RE.search(soru):
            kanun_no = km.group(1)
        else:
            for kis, no in KISALTMALAR.items():
                if re.search(rf"\b{kis}\b", soru, re.IGNORECASE):
                    kanun_no = no
                    break

        adaylar = [k for k in (self._bm25_kayitlar or self.store.tum_kayitlar())
                   if k.get("madde_no") == madde_no
                   and (kanun_no is None or k.get("mevzuat_no") == kanun_no)]
        return adaylar[:limit]

    def _ham_benzerlik(self, soru: str, mulga_haric: bool = True) -> float:
        """Kullanicinin ham sorusunun kulliyata en yakin benzerligi.

        Sorunun kulliyatla ilgili olup olmadiginin olcusu budur. Genisletilmis
        sorgudan olculemez: genisletme hukuk terimleri ekledigi icin alakasiz
        sorular da yuksek puan aliyor.
        """
        v = self.embedder.encode_query(soru)
        s = self.store.search(v, limit=1, mulga_haric=mulga_haric)
        puan = s[0]["skor"] if s else 0.0
        self._ham_puan_sabit = puan
        return puan

    # ---------- birlestirme ----------
    def ara(self, soru: str, limit: int = 5, aday: int | None = None,
            mulga_haric: bool = True) -> list[dict]:
        """Sorguyu arar ve en alakali maddeleri doner.

        Sorgu genisletme UYARLAMALI calisir: her sorguda degil, yalnizca ilk
        arama zayif sonuc verdiginde. Genisletme isabeti artiriyor (23/34 ->
        25/34) ama sorgu basina 30 saniye ekliyordu; bedeli yalnizca ihtiyaci
        olan sorgular odesin.
        """
        # Her sorguda genisletme aciksa ilk arama gereksiz: genisletici
        # "orijinal sorgu + hukuk terimleri" donduruyor, yani TEK arama
        # ikisini de kapsiyor. Olculdu -- iki aramali akis sorgu basina
        # 14.3 saniye suruyordu ve 3.4 saniyesi bu atilabilir ilk aramaydi.
        # Sorgunun nasil anlasildigini disariya aciyoruz. Kullanici
        # sistemin kendisini dogru anlayip anlamadigini goremezse, bos gelen
        # bir sonucun sebebini de bilemiyor -- soru mu kotu, kulliyat mi
        # eksik, ayirt edemiyor.
        self.son_genisletme = None
        if config.SORGU_GENISLET and config.GENISLET_HEP:
            # Guven puani KULLANICININ sorusundan olculur, genisletilmisten
            # degil. Genisletme hukuk terimleri ekliyor ve alakasiz bir soru
            # da yuksek benzerlik aliyor -- olculdu: "kahve nasil demlenir"
            # ham sorguda 0.631, genisletilmis sorguda 0.728.
            ham = self._ham_benzerlik(soru, mulga_haric)
            self.son_vektor_puani = ham
            # Guclu sorguda genisletme atlanir: olculdu, genisletme sorgu
            # basina 4.09 saniye ekliyor ve zaten dogru maddeyi bulan bir
            # sorguda faydasi yok.
            if ham >= config.GENISLET_YETER:
                return self._ara_bir_kez(soru, limit, aday, mulga_haric)
            genis = self.genisletici.genislet(soru)
            if genis != soru:
                self.son_genisletme = genis
            sonuc = self._ara_bir_kez(genis, limit, aday, mulga_haric)
            self.son_vektor_puani = self._ham_puan_sabit
            return sonuc

        sonuc = self._ara_bir_kez(soru, limit, aday, mulga_haric)

        if not config.SORGU_GENISLET:
            return sonuc

        if not self._zayif_mi(sonuc):
            return sonuc

        genis = self.genisletici.genislet(soru)
        if genis == soru:                 # genisletme basarisiz oldu
            return sonuc
        self.son_genisletme = genis

        log.debug("zayif sonuc, genisletilmis sorguyla tekrar araniyor")
        yeni = self._ara_bir_kez(genis, limit, aday, mulga_haric)
        # Ikisinden hangisi daha guclu puanliysa o doner
        return yeni if self._en_iyi_puan(yeni) > self._en_iyi_puan(sonuc) else sonuc

    @staticmethod
    def _en_iyi_puan(sonuc: list[dict]) -> float:
        return max((k.get("ce_skor", k.get("skor", 0.0)) for k in sonuc), default=0.0)

    def _zayif_mi(self, sonuc: list[dict]) -> bool:
        """En iyi adayin cross-encoder puani esigin altindaysa sonuc zayiftir.

        Cross-encoder puani, "bu madde bu soruya cevap veriyor mu" sorusunun
        karsiligi. Dusuk puan, dogru maddenin bulunamadigina isaret eder.
        """
        if not sonuc:
            return True
        return self._en_iyi_puan(sonuc) < config.GENISLET_ESIK

    def _ara_bir_kez(self, soru: str, limit: int, aday: int | None,
                     mulga_haric: bool) -> list[dict]:
        # Yeniden siralama acikken ilk asama daha genis aday toplamali:
        # cross-encoder yalnizca onune gelen adaylari siralayabilir, pencereye
        # hic girmemis bir maddeyi kurtaramaz.
        if aday is None:
            aday = max(config.RERANK_ADAY, 20) if self.rerank else 20

        # Aksansiz yazilmis sorguyu gercek yazimina cevir. BM25 katlama
        # sayesinde zaten calisiyordu ama vektor ve cross-encoder ham metni
        # aldigi icin "hirsizlik" ile "hırsızlık" arasindaki farka takiliyordu.
        if config.YAZIM_DUZELT:
            duzeltilmis = self.yazim.duzelt(soru)
            if duzeltilmis != soru:
                log.debug("sorgu duzeltildi: %r -> %r", soru, duzeltilmis)
                soru = duzeltilmis

        siralar: dict[str, dict] = {}

        def ekle(kayitlar: list[dict], agirlik: float, kaynak: str) -> None:
            for rank, k in enumerate(kayitlar):
                cid = k.get("chunk_id")
                if not cid:
                    continue
                giris = siralar.setdefault(cid, {"kayit": k, "skor": 0.0, "kaynaklar": []})
                giris["skor"] += agirlik / (60 + rank)   # RRF
                giris["kaynaklar"].append(kaynak)

        # 1) Dogrudan madde numarasi -- en guvenilir, en yuksek agirlik
        ekle(self._dogrudan_madde(soru), agirlik=3.0, kaynak="madde_no")

        # 2) Anlamsal
        vek = self.embedder.encode_query(soru)
        vektor_sonuc = self.store.search(vek, limit=aday, mulga_haric=mulga_haric)
        # En iyi HAM benzerlik, sorunun kulliyatla ilgili olup olmadiginin
        # olcusu. Yeniden siralayicinin puani bu is icin kullanilamaz --
        # o, aday havuzu icinde siralama yapar ve havuzda hep bir en iyi
        # vardir; olculdu, "kahve nasil demlenir" 0.970 aliyor.
        self.son_vektor_puani = vektor_sonuc[0]["skor"] if vektor_sonuc else 0.0
        ekle(vektor_sonuc, agirlik=1.0, kaynak="vektor")

        # 2b) Cekirdek sorgu: soru kaliplari atilmis hali. Ayri bir sinyal
        # olarak ekleniyor, asil sorgunun yerini almiyor.
        if config.CEKIRDEK_SORGU and (cekirdek := cekirdek_sorgu(soru)):
            cv = self.embedder.encode_query(cekirdek)
            ekle(self.store.search(cv, limit=aday, mulga_haric=mulga_haric),
                 agirlik=config.CEKIRDEK_AGIRLIK, kaynak="cekirdek")

        # 3) Anahtar kelime
        if (bm25 := self.bm25) is not None:
            skorlar = bm25.get_scores(self._tokenize(soru))
            en_iyi = sorted(range(len(skorlar)), key=lambda i: skorlar[i], reverse=True)[:aday]
            ekle([self._bm25_kayitlar[i] for i in en_iyi], agirlik=1.0, kaynak="bm25")

        sirali = sorted(siralar.values(), key=lambda x: x["skor"], reverse=True)
        birlesik = [{**s["kayit"], "skor": s["skor"],
                     "kaynaklar": sorted(set(s["kaynaklar"]))}
                    for s in sirali]

        if not self.rerank:
            return birlesik[:limit]

        # Cross-encoder yavas oldugu icin tum kulliyata degil, yalnizca ilk
        # asamanin getirdigi adaylara uygulanir. RERANK_ADAY bu pencerenin
        # genisligi: dar tutulursa dogru madde pencereye hic giremez, genis
        # tutulursa sorgu yavaslar.
        pencere = birlesik[:max(config.RERANK_ADAY, limit)]
        try:
            return self.reranker.sirala(soru, pencere, limit)
        except Exception as exc:
            log.warning("yeniden siralama basarisiz, temel siralama kullaniliyor: %s", exc)
            return birlesik[:limit]
