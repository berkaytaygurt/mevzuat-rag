"""Yargitay Karar Arama (karararama.yargitay.gov.tr) istemcisi.

Site uc uctan calisiyor:
  POST /arama       -> aramayi baslatir (oturumda sorguyu kurar)
  POST /aramalist   -> sonuc listesi (id + daire + esas/karar no + tarih)
  GET  /getDokuman?id=  -> kararin tam metni (JSON icinde HTML)

GOVDE SEKLI ONEMLI. Sayfada bir de /aramadetaylist ucu var ve o, on besten
fazla alan bekliyor; eksik ya da fazla alanla "ADALET_RUNTIME_EXCEPTION"
donduruyor. Basit arama ise yalnizca dort alan gonderiyor. Ilk denemede
detayli uca genis bir govde gonderdigimiz icin istekler surekli hata verdi ve
bu, WAF engeli sanildi. Dogru govde tarayicida gercek bir arama yapilip
sitenin kendi istegi izlenerek bulundu.

Not: Site, kendini bot olarak tanitan istekleri reddediyor; tarayici benzeri
bir User-Agent gerekiyor. Buna karsilik hizda nazik davraniyoruz: istekler
arasinda bekleme var, her belge diske onbelleklenir ve ikinci kez istenmez.
Mahkeme kararlari FSEK m.31 uyarinca telif korumasina tabi degildir.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

import config

log = logging.getLogger(__name__)

TABAN = "https://karararama.yargitay.gov.tr"
BASLAT_UCU = f"{TABAN}/arama"
ARAMA_UCU = f"{TABAN}/aramalist"
BELGE_UCU = f"{TABAN}/getDokuman"

TARAYICI_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


@dataclass
class KararKaydi:
    id: str
    daire: str
    esas_no: str
    karar_no: str
    karar_tarihi: str
    durum: str = ""
    anahtar: str = ""          # hangi aramadan geldi
    metin: str = ""

    @property
    def chunk_id(self) -> str:
        return f"karar-{self.id}"

    @property
    def kisa_ad(self) -> str:
        """Cevapta gosterilecek atif: 'Yargitay 9. HD 2024/1234 E.'"""
        daire = re.sub(r"\s+", " ", self.daire).strip()
        return f"{daire} {self.esas_no} E. {self.karar_no} K."

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunk_id"] = self.chunk_id
        d["kisa_ad"] = self.kisa_ad
        return d


class EmsalClient:
    def __init__(self, delay: float = 2.0, cache_dir: Path | None = None):
        # Sessiz kayip sayaci. Neden var: 1.253 belge "alinamadi" diye
        # dustu ve bu YALNIZCA satir satir WARNING olarak gorunuyordu;
        # sebep (429) ise log.debug'daydi, yani hic goze carpmiyordu.
        # Toplam ozet olmadan %17'lik kayip fark edilmiyor.
        self.sayac = {"belge_ok": 0, "belge_hata": 0, "hiz_siniri": 0,
                      "arama_hata": 0}
        self.delay = delay
        self.cache_dir = cache_dir or (config.RAW_DIR / "karar_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._son_istek = 0.0

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": TARAYICI_UA,
            "Accept-Language": "tr-TR,tr;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=utf-8",
            "Referer": f"{TABAN}/",
        })
        self.session.verify = False
        # Oturum cerezi al; ilk istek cerezsiz gidince sunucu hata donduruyor
        try:
            self.session.get(f"{TABAN}/", timeout=30)
        except requests.RequestException as exc:
            log.warning("acilis sayfasi alinamadi: %s", exc)

    def _bekle(self) -> None:
        gecen = time.monotonic() - self._son_istek
        if gecen < self.delay:
            time.sleep(self.delay - gecen)
        self._son_istek = time.monotonic()

    # ---------- arama ----------
    @staticmethod
    def _arama_govdesi(kelime: str, sayfa: int, boyut: int) -> dict:
        """Sitenin kendi gonderdigi govde: yalnizca dort alan.

        Fazla alan eklemek hataya yol aciyor; sadelik burada zorunluluk.
        """
        return {"data": {
            "aranan": kelime, "arananKelime": kelime,
            "pageSize": boyut, "pageNumber": sayfa,
        }}

    def _aramayi_baslat(self, kelime: str) -> None:
        """Sitenin akisinda listeden once bu cagri yapiliyor."""
        self._bekle()
        try:
            self.session.post(BASLAT_UCU,
                              json={"data": {"aranan": kelime, "arananKelime": kelime}},
                              timeout=60)
        except requests.RequestException as exc:
            log.debug("arama baslatilamadi (%s): %s", kelime, exc)

    def _istek_dene(self, url: str, govde: dict, etiket: str,
                    deneme: int = 7) -> dict | None:
        """Arama istegini tekrar deneyerek yapar.

        Sunucu ayni gövdeye bazen sonuc, bazen "ADALET_RUNTIME_EXCEPTION"
        donduruyor; hata parametreye degil ana bagli. Tek denemede vazgecmek
        sayfalarin rastgele bosalmasina yol aciyordu.

        DENEME SAYISI 4'TEN 7'YE CIKARILDI. 55 anahtarlik cekimde biten
        49 anahtarin 16'si (%33) "4 denemede sonuc vermedi" ile BOS
        dondu -- o anahtardan hic karar gelmedi. Ucu elle yeniden
        denendi, ucu de ANINDA sonuc verdi (1,1 milyon / 388 bin / 485
        bin kayit). Yani hata kalici degil, anlik. Dogrusal bekleme ile
        4 deneme ~15 saniye ediyordu; sitenin toparlanmasi icin kisa.
        Ustel ve ust sinirli bekleme (2,5/5/10/20/30/30 sn) toplami
        ~100 saniyeye cikariyor. Bir anahtarin 60 kararini tumden
        kaybetmektense beklenir.
        """
        for i in range(deneme):
            self._bekle()
            try:
                cevap = self.session.post(url, json=govde, timeout=60)
                cevap.raise_for_status()
                veri = (cevap.json() or {}).get("data")
                if isinstance(veri, dict):
                    return veri
            except (requests.RequestException, ValueError) as exc:
                log.debug("istek hatasi (%s): %s", etiket, exc)
            if i < deneme - 1:
                # Ustel, ust sinirli: dogrusal artis yeterince beklemiyordu.
                time.sleep(min(self.delay * (2 ** i), 30.0))
        self.sayac["arama_hata"] += 1
        log.warning("arama %d denemede sonuc vermedi: %s", deneme, etiket)
        return None

    def ara(self, kelime: str, *, en_fazla: int = 500,
            sayfa_boyu: int = 100) -> list[KararKaydi]:
        """Bir anahtar kelime icin karar listesi doner (metin haric)."""
        kayitlar: list[KararKaydi] = []
        sayfa = 1
        toplam = None
        self._aramayi_baslat(kelime)

        while len(kayitlar) < en_fazla:
            govde = self._arama_govdesi(kelime, sayfa, sayfa_boyu)
            veri = self._istek_dene(ARAMA_UCU, govde, f"{kelime} s.{sayfa}")
            if veri is None:
                break

            if toplam is None:
                toplam = veri.get("recordsTotal") or 0
                log.info("'%s': %s karar bulundu", kelime, f"{toplam:,}")

            satirlar = veri.get("data") or []
            if not satirlar:
                break

            for r in satirlar:
                kayitlar.append(KararKaydi(
                    id=str(r.get("id", "")),
                    daire=(r.get("daire") or "").strip(),
                    esas_no=(r.get("esasNo") or "").strip(),
                    karar_no=(r.get("kararNo") or "").strip(),
                    karar_tarihi=(r.get("kararTarihi") or "").strip(),
                    durum=(r.get("durum") or "").strip(),
                    anahtar=kelime,
                ))

            sayfa += 1
            if toplam and len(kayitlar) >= toplam:
                break

        return kayitlar[:en_fazla]

    # ---------- belge ----------
    def _cache_yolu(self, karar_id: str) -> Path:
        ad = hashlib.sha1(karar_id.encode()).hexdigest()[:16]
        return self.cache_dir / f"{ad}.json"

    def ozet(self) -> str:
        """Cekim sonunda TEK satirda ne kaybedildigini soyler.

        Bu metot bir hatanin bedeliyle yazildi: 1.253 belge dustu ve
        cekim "basarili" gorundu, cunku her kayip ayri bir WARNING
        satiriydi ve binlerce satirlik logda kayboluyordu. Sebep (429
        Too Many Requests) ise DEBUG duzeyindeydi, hic yazilmiyordu.
        Bir daha sessizce olmasin diye toplamlar burada.
        """
        s = self.sayac
        toplam = s["belge_ok"] + s["belge_hata"]
        oran = (100.0 * s["belge_hata"] / toplam) if toplam else 0.0
        parcalar = [f"belge {s['belge_ok']}/{toplam} indi"]
        if s["belge_hata"]:
            parcalar.append(f"DUSEN {s['belge_hata']} (%{oran:.1f})")
        if s["hiz_siniri"]:
            parcalar.append(f"429 hiz siniri {s['hiz_siniri']} kez")
        if s["arama_hata"]:
            parcalar.append(f"arama basarisiz {s['arama_hata']}")
        return " | ".join(parcalar)

    # 429 gorunce beklenecek sure (saniye). Site Retry-After BASLIGI
    # GONDERMIYOR -- olculdu, 429 cevabinda hicbir ipucu yok -- bu yuzden
    # sure elle secildi. Kisa tutmanin bedeli agir: asagiya bak.
    HIZ_SINIRI_BEKLEME = 45.0

    def belge(self, karar_id: str) -> str:
        """Kararin tam metnini doner. Onbellekteyse ag istegi yapilmaz.

        NEDEN BU KADAR SABIRLI
        55 anahtarlik cekimde 1.253 belge "alinamadi" diye dustu --
        indirilenlerin yaklasik %17'si. Once belgelerin gercekten yok
        oldugu sanildi. Degildi: elle bakildiginda sunucu

            429 Client Error: Too Many Requests

        donuyordu ve ayni belge tek basina istendiginde 2.569 karakterlik
        metni sorunsuz veriyordu. Yani karar duruyor, biz cok hizli
        soruyoruz. Eski hal 3 deneme + dogrusal bekleme = toplam 7,5
        saniye idi; hiz siniri penceresi bundan uzun, dolayisiyla ucu de
        ayni pencereye dusuyor ve karar SESSIZCE kayboluyordu.

        Simdi 429 ayri ele aliniyor: normal hatadan cok daha uzun
        bekleniyor, cunku 429 "istek bozuk" degil "yavasla" demek.
        """
        onbellek = self._cache_yolu(karar_id)
        if onbellek.exists():
            return json.loads(onbellek.read_text(encoding="utf-8")).get("metin", "")

        ham = ""
        deneme = 6
        for i in range(deneme):
            self._bekle()
            hiz_siniri = False
            try:
                r = self.session.get(BELGE_UCU, params={"id": karar_id}, timeout=60)
                hiz_siniri = r.status_code == 429
                if hiz_siniri:
                    self.sayac["hiz_siniri"] += 1
                r.raise_for_status()
                ham = (r.json() or {}).get("data") or ""
                if ham:
                    break
            except (requests.RequestException, ValueError) as exc:
                log.debug("belge hatasi (%s): %s", karar_id, exc)
            if i < deneme - 1:
                if hiz_siniri:
                    # Pencerenin kapanmasini bekle; ustel artirmak yerine
                    # sabit ve uzun, cunku sorun hiz -- kararsizlik degil.
                    time.sleep(self.HIZ_SINIRI_BEKLEME)
                else:
                    time.sleep(min(self.delay * (2 ** i), 30.0))
        if not ham:
            self.sayac["belge_hata"] += 1
            log.warning("belge alinamadi: %s", karar_id)
            return ""
        self.sayac["belge_ok"] += 1

        metin = _html_metne(ham)
        onbellek.write_text(json.dumps({"id": karar_id, "metin": metin},
                                       ensure_ascii=False), encoding="utf-8")
        return metin


def _html_metne(ham: str) -> str:
    """getDokuman HTML dondurur; etiketleri atip duz metne cevirir."""
    if not ham:
        return ""
    if "<" in ham:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(ham, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        ham = soup.get_text("\n", strip=True)
    ham = ham.replace("\xa0", " ")
    ham = re.sub(r"[ \t]+", " ", ham)
    return re.sub(r"\n{3,}", "\n\n", ham).strip()
