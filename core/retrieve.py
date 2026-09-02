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

# Madde referansi: "madde 19", "m.3/A", "19. madde", "gecici madde 5".
# Onek bicimde ("19 madde") sira eki ZORUNLU tutuldu; aksi halde
# "4857 madde 19" sorgusunda 4857 madde numarasi saniliyordu.
MADDE_REF_RE = re.compile(
    r"(?:(?P<tip1>ek|geçici|gecici|mükerrer|mukerrer)\s+)?"
    r"(?:madde|m\.|mad\.)\s*(?P<no1>\d+(?:\s*/\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])?)"
    r"|(?:(?P<tip2>ek|geçici|gecici|mükerrer|mukerrer)\s+)?"
    r"(?P<no2>\d+(?:\s*/\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])?)\s*"
    r"(?:\.|inci|nci|uncu|üncü|ıncı)\s*madde",
    re.IGNORECASE)

# Kanun numarasi. "sayili" kelimesini sart kosmak avukatin yazdigi bicimlerin
# cogunu kaciriyordu: "4857 madde 19", "6098 Kanunu m.344" gibi.
KANUN_NO_RE = re.compile(
    r"\b(?P<a>\d{3,5})\s*(?:sayılı|sayili|say\.)"
    r"|\b(?P<b>\d{3,5})\s*(?:sayılı|sayili)?\s*kanunu?\b"
    # "4857 madde 19" / "4857 geçici madde 6": sayidan hemen sonra madde
    # referansi geliyorsa o sayi kanun numarasidir.
    r"|\b(?P<c>\d{3,5})\s*"
    r"(?=(?:ek|geçici|gecici|mükerrer|mukerrer)?\s*(?:madde|m\.|mad\.))",
    re.IGNORECASE)

# Kisaltma ve kanun adi -> numara. Avukat kanunu numarayla degil adiyla
# aniyor ("TBK 344", "Is Kanunu 19. madde"). Ad taninmayinca dogrudan madde
# yolu bos donuyor, arama da yalnizca madde NUMARASINA bakip yanlis kanunun
# maddesini 1. siraya cikariyordu -- olculdu: "4857 madde 19" -> 5285 m.19,
# "TMK 166" -> 5905 m.166, "TBK 344" -> 6102 m.344.
KISALTMALAR = {
    "tbk": "6098", "tmk": "4721", "tck": "5237", "hmk": "6100",
    "ttk": "6102", "cmk": "5271", "ik": "4857", "iyuk": "2577",
    "vuk": "213", "kvkk": "6698", "ikk": "6331", "iik": "2004",
    "türk borçlar kanunu": "6098", "borçlar kanunu": "6098",
    "türk medeni kanunu": "4721", "medeni kanunu": "4721",
    "medeni kanun": "4721", "türk ceza kanunu": "5237",
    "ceza kanunu": "5237", "iş kanunu": "4857",
    "hukuk muhakemeleri kanunu": "6100", "türk ticaret kanunu": "6102",
    "ticaret kanunu": "6102", "ceza muhakemesi kanunu": "5271",
    "icra ve iflas kanunu": "2004", "vergi usul kanunu": "213",
    "idari yargılama usulü kanunu": "2577",
    "kişisel verilerin korunması kanunu": "6698",
    "iş sağlığı ve güvenliği kanunu": "6331",
    "sosyal sigortalar ve genel sağlık sigortası kanunu": "5510",
    "avukatlık kanunu": "1136", "kabahatler kanunu": "5326",
    "tüketicinin korunması hakkında kanun": "6502",
}

# Turkce harf -> ASCII karsiligi
_TR_HARITA = str.maketrans({
    "ş": "s", "Ş": "s", "ı": "i", "I": "i", "İ": "i", "i": "i",
    "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c", "â": "a", "Â": "a", "î": "i", "Î": "i",
    "û": "u", "Û": "u",
    # Birlesik nokta: Python "İ".lower() harfi "i" + U+0307 diye ikiye
    # ayiriyor. Katlamada dusurulmezse ayni kelimenin iki ayri bicimi olusuyor.
    "̇": None,
})


def _tr_katla(metin: str) -> str:
    """Turkce harfleri ASCII'ye katlar ve kucultur.

    Kullanicilar sorgularini cogunlukla Turkce karakter kullanmadan yazar
    ("kisisel veri"). Katlama olmadan BM25 "kisisel" ile "kisisel"i (s vs s)
    eslestiremiyor ve birebir baslik eslesmesi olan madde hic getirilemiyordu.
    Indeks ve sorgu tarafinda ayni katlama uygulanmali.
    """
    return metin.translate(_TR_HARITA).lower()


# Kisaltma tablosunun aksansiz hali. Uzun ad once denenir ki "turk ceza
# kanunu" arayan sorgu "ceza kanunu" girdisine dusup ayni numarayi bulsa da
# yanlis konumdan eslesmesin.
KISALTMALAR_KATLI = {_tr_katla(ad): no for ad, no in KISALTMALAR.items()}
_KISALTMA_SIRALI = sorted(KISALTMALAR_KATLI, key=len, reverse=True)


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
        self.son_meseleler: list[str] = []

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
        del tokenlar
        self.bm25_yol.parent.mkdir(parents=True, exist_ok=True)

        # Kayitlar pickle'a KONMUYOR: kayitlar.json'un birebir kopyasiydi
        # (367 MB) ve pickle.dump 275 bin maddede MemoryError veriyordu.
        # Yerine yalnizca sayi yaziliyor; okurken depodan gelen listeyle
        # karsilastirilip hizalama dogrulaniyor.
        #
        # Yazim ATOMIK: onceki surumde dogrudan hedef dosyaya yaziliyordu ve
        # dump ortasinda patlayinca bm25.pkl 599 MB'tan 69 MB'a dusup
        # aramanin BM25 yarisini tumuyle bozdu.
        import os
        gecici = self.bm25_yol.with_suffix(self.bm25_yol.suffix + ".tmp")
        with open(gecici, "wb") as f:
            pickle.dump({"bm25": bm25, "kayit_sayisi": len(kayitlar)}, f,
                        protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(gecici, self.bm25_yol)
        self._bm25, self._bm25_kayitlar = bm25, kayitlar
        log.info("BM25 indeksi kuruldu: %d madde", len(kayitlar))

    @property
    def bm25(self):
        if self._bm25 is None and self.bm25_yol.exists():
            with open(self.bm25_yol, "rb") as f:
                d = pickle.load(f)
            kayitlar = d.get("kayitlar")        # eski bicim: liste iceride
            if kayitlar is None:
                kayitlar = self.store.tum_kayitlar()
                # Hizalama sart: BM25 sirasi kayit sirasiyla ayni olmazsa
                # arama calisir ama YANLIS maddeleri doner. Uyusmuyorsa
                # BM25'i hic kullanmamak, sessizce sacmalamaktan iyidir.
                if len(kayitlar) != d.get("kayit_sayisi"):
                    log.error("BM25 indeksi kulliyatla uyusmuyor (%s vs %s); "
                              "'python cli.py bm25' ile yeniden kurun",
                              d.get("kayit_sayisi"), len(kayitlar))
                    return None
            self._bm25, self._bm25_kayitlar = d["bm25"], kayitlar
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
    @staticmethod
    def _kanun_bul(soru: str) -> tuple[str | None, int]:
        """Sorudaki kanunu bulur; (numara, referansin bittigi konum) doner.

        Ad/kisaltma ONCE denenir. Sayi kaliplari once denenirse "TMK 166
        maddesi" sorgusunda 166 kanun numarasi saniliyor -- oysa orada
        kanun zaten adiyla yazilmis.
        """
        katli = _tr_katla(soru)
        for ad in _KISALTMA_SIRALI:
            if m := re.search(rf"\b{re.escape(ad)}\b", katli):
                return KISALTMALAR_KATLI[ad], m.end()
        if km := KANUN_NO_RE.search(soru):
            return (km.group("a") or km.group("b") or km.group("c")), km.end()
        return None, 0

    @staticmethod
    def _madde_bul(soru: str, ad_sonu: int) -> str | None:
        """Madde referansini kulliyattaki yazilisa cevirir ("m.3/a" -> "3/A")."""
        no = tip = ""
        if m := MADDE_REF_RE.search(soru):
            no = m.group("no1") or m.group("no2") or ""
            tip = m.group("tip1") or m.group("tip2") or ""
        elif ad_sonu:
            # "TBK 344", "TMK 166 maddesi" -- sayi kanun adindan hemen sonra
            # geliyor ve sira eki yok. Bu bicim yalnizca kanun ZATEN bulunmus
            # ve geri kalan sadece bu sayiysa kabul edilir.
            if s := re.match(r"[\s,.:]*(\d+(?:\s*/\s*[a-zA-ZçğıöşüÇĞİÖŞÜ])?)"
                             r"\s*(?:\.|inci|nci|uncu|üncü|ıncı)?"
                             r"\s*(?:madde\w*)?\s*$",
                             soru[ad_sonu:], re.IGNORECASE):
                no = s.group(1)
        if not no:
            return None
        tip = {"gecici": "Geçici", "geçici": "Geçici", "ek": "Ek",
               "mukerrer": "Mükerrer", "mükerrer": "Mükerrer"}.get(tip.lower(), "")
        no = re.sub(r"\s+", "", no).upper()
        return f"{tip} {no}".strip()

    def _dogrudan_madde(self, soru: str, limit: int = 3) -> list[dict]:
        kanun_no, ad_sonu = self._kanun_bul(soru)
        madde_no = self._madde_bul(soru, ad_sonu)
        # Kanun bilinmiyorsa bu yol KULLANILMAZ. Eskiden ayni numarayi tasiyan
        # rastgele bir kanunun maddesi donuyordu; bu yol RRF'te en yuksek
        # agirligi (3.0) tasidigi icin de dogruca 1. siraya cikiyordu.
        if madde_no is None or kanun_no is None:
            return []
        return [k for k in (self._bm25_kayitlar or self.store.tum_kayitlar())
                if k.get("madde_no") == madde_no
                and k.get("mevzuat_no") == kanun_no][:limit]

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
            # Cok olgulu soru: meselelere ayirip her birini ayri ara.
            # Tek vektor, olgularin bulanik ortalamasi oluyor ve hicbirinin
            # maddesini bulamiyor -- olculdu, "isci 4 yil 11 ay calisti,
            # devamsizlik nedeniyle savunma almadan feshetti" sorusunda
            # sistem "dayanak bulamadim" dedi, oysa cevap m.19'daydi.
            if config.MESELE_AYIR:
                cok = self._mesele_araması(soru, limit, aday, mulga_haric)
                if cok is not None:
                    return cok

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

    def _mesele_araması(self, soru: str, limit: int, aday, mulga_haric):
        """Cok olgulu soruyu meselelere ayirip birlestirilmis sonuc doner.

        Ayrilamiyorsa None doner; cagiran taraf normal akisa devam eder.
        """
        from .mesele import cok_olgulu_mu, meseleleri_ayir

        if not cok_olgulu_mu(soru):
            return None
        meseleler = meseleleri_ayir(soru, self.genisletici.uretici)
        if not meseleler:
            return None

        self.son_meseleler = meseleler
        log.debug("soru %d meseleye ayrildi: %s", len(meseleler), meseleler)

        # Her mesele ayri aranip RRF ile birlestiriliyor. Ilk siradaki
        # mesele biraz daha agir: genelde sorunun asil konusu.
        birlesik: dict[str, dict] = {}
        for i, m in enumerate(meseleler):
            agirlik = 1.0 if i == 0 else 0.85
            for rank, k in enumerate(self._ara_bir_kez(m, limit, aday, mulga_haric)):
                cid = k.get("chunk_id")
                if not cid:
                    continue
                g = birlesik.setdefault(cid, {"kayit": k, "skor": 0.0})
                g["skor"] += agirlik / (60 + rank)

        sirali = sorted(birlesik.values(), key=lambda x: -x["skor"])
        return [{**g["kayit"], "skor": g["skor"]} for g in sirali[:limit]]

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
        dogrudan = self._dogrudan_madde(soru)
        ekle(dogrudan, agirlik=3.0, kaynak="madde_no")

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
            return self._one_sabitle(dogrudan, birlesik, birlesik, limit)

        # Cross-encoder yavas oldugu icin tum kulliyata degil, yalnizca ilk
        # asamanin getirdigi adaylara uygulanir. RERANK_ADAY bu pencerenin
        # genisligi: dar tutulursa dogru madde pencereye hic giremez, genis
        # tutulursa sorgu yavaslar.
        pencere = birlesik[:max(config.RERANK_ADAY, limit)]
        try:
            sirali_sonuc = self.reranker.sirala(soru, pencere, limit)
        except Exception as exc:
            log.warning("yeniden siralama basarisiz, temel siralama kullaniliyor: %s", exc)
            sirali_sonuc = birlesik[:limit]
        return self._one_sabitle(dogrudan, sirali_sonuc, birlesik, limit)

    @staticmethod
    def _one_sabitle(dogrudan: list[dict], sonuc: list[dict],
                     birlesik: list[dict], limit: int) -> list[dict]:
        """Numarayla istenen maddeyi listenin basina sabitler.

        Avukat "4857 madde 19" yazdiginda o madde bir TAHMIN degil, istegin
        kendisi. Ama boyle bir sorguda anlamsal icerik yok; cross-encoder
        maddeyi asagi itiyordu. Olculdu: "4857 madde 19" sorgusunda dogru
        madde ilk 5'te hic yoktu, 1. sirada 5285 m.19 duruyordu -- dogru
        numara, yanlis kanun.
        """
        if not dogrudan:
            return sonuc[:limit]
        kimlikler = {k.get("chunk_id") for k in dogrudan}
        # Once yeniden siralanmis surumu al (puan alanlarini tasiyor),
        # pencereye girmediyse birlesik listeden tamamla.
        onde = [k for k in sonuc if k.get("chunk_id") in kimlikler]
        eksik = kimlikler - {k.get("chunk_id") for k in onde}
        onde += [k for k in birlesik if k.get("chunk_id") in eksik]
        kalan = [k for k in sonuc if k.get("chunk_id") not in kimlikler]
        return (onde + kalan)[:limit]
