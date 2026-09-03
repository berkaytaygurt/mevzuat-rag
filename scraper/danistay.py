"""Danistay Karar Arama (karararama.danistay.gov.tr) istemcisi.

NEDEN VAR
Kulliyatta yalnizca Yargitay karari vardi. Memur, disiplin, atama, mobbing
gibi uyusmazliklar IDARI YARGIYA gidiyor ve o kararlar Danistay'da. Sistem
"kadrolu ogretmene mobbing" gibi bir soruda zayif kaliyordu: TBK m.417
geliyordu ama o hukum ISCI icin, memura dogrudan uygulanmaz.

UCLAR (tarayicida gercek bir arama izlenerek bulundu)
    POST /arama       -> aramayi oturumda kurar, tablo iskeletini doner
    POST /aramalist   -> sonuc listesi (id, daireKurul, esas/karar no, tarih)
    GET  /getDokuman?id=&arananKelime=  -> kararin tam metni (HTML)

GOVDE SEKLI YARGITAY'DAN FARKLI. Yargitay tekil "aranan"/"arananKelime"
alanlari bekliyor; Danistay COGUL VE DIZI bekliyor:

    andKelimeler = ["\"mobbing\""]        <- deger tirnak icinde
    orKelimeler, notAndKelimeler, notOrKelimeler

Tekil "andKelime" gonderince sunucu "Lutfen arama kriterlerini giriniz!"
diyor. Bu, sitenin kendi betigindeki formData kurulumundan okundu.

CAPTCHA SINIRI -- ONEMLI
Sitede reCAPTCHA var ve sunucu istedigi anda devreye sokabiliyor
(sayfadaki isDisplayCaptcha bayragi). Su an kapali. Acilirsa bu istemci
DURUR: captcha cozmeye ya da bot denetimini atlatmaya calismaz. Boyle bir
durumda `CaptchaAcik` firlatilir ve isi insan devralir.

Hizda nazik davraniliyor: istekler arasinda bekleme var, her belge diske
onbelleklenir ve ikinci kez istenmez. Mahkeme kararlari FSEK m.31 uyarinca
telif korumasina tabi degildir.
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

TABAN = "https://karararama.danistay.gov.tr"
BASLAT_UCU = f"{TABAN}/arama"
ARAMA_UCU = f"{TABAN}/aramalist"
BELGE_UCU = f"{TABAN}/getDokuman"

TARAYICI_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Sunucu captcha isteyip istemedigini IKI ayri yerde bildiriyor:
#   1. Sayfada bir bayrak (sitenin kendi isDisplayCaptcha() fonksiyonu bunu okur)
#   2. API cevabinda metadata.FMTE icinde "DisplayCaptcha" -- olculdu, cekim
#      sirasinda tam olarak boyle geldi ve bizim ilk denetimimiz bunu
#      kacirdigi icin sonraki anahtarlar sessizce bos dondu.
# (?<!is): sayfadaki "isDisplayCaptcha" kimligi her zaman var ve degeri
# false olabilir; onu captcha sanmamak icin yalnizca bagimsiz gecen
# "DisplayCaptcha" yakalaniyor.
CAPTCHA_BAYRAGI_RE = re.compile(
    r"""id\s*=\s*["']isDisplayCaptcha["'][^>]*>\s*true|(?<!is)DisplayCaptcha""",
    re.IGNORECASE)


class CaptchaAcik(RuntimeError):
    """Sunucu captcha istedi. Cozmeye calismiyoruz; is durur."""


@dataclass
class DanistayKarari:
    id: str
    daire: str
    esas_no: str
    karar_no: str
    karar_tarihi: str
    anahtar: str = ""
    metin: str = ""

    @property
    def chunk_id(self) -> str:
        return f"danistay-{self.id}"

    @property
    def kisa_ad(self) -> str:
        daire = re.sub(r"\s+", " ", self.daire).strip()
        return f"Danıştay {daire} {self.esas_no} E. {self.karar_no} K."

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunk_id"] = self.chunk_id
        d["kisa_ad"] = self.kisa_ad
        d["mahkeme"] = "Danıştay"
        return d


def _bos_govde() -> dict:
    """Sitenin gonderdigi alanlarin tamami. Eksik alan hataya yol aciyor."""
    return {
        "andKelimeler": [], "orKelimeler": [],
        "notAndKelimeler": [], "notOrKelimeler": [],
        "daire": "", "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
        "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
        "baslangicTarihi": "", "bitisTarihi": "",
        "mevzuatNumarasi": "", "mevzuatAdi": "", "madde": "",
        "siralama": "1", "siralamaDirection": "desc",
    }


class DanistayClient:
    def __init__(self, delay: float = 2.0, cache_dir: Path | None = None):
        self.delay = delay
        self.cache_dir = cache_dir or (config.RAW_DIR / "danistay_cache")
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
        try:
            acilis = self.session.get(f"{TABAN}/", timeout=30)
            self._captcha_denetle(acilis.text)
        except requests.RequestException as exc:
            log.warning("acilis sayfasi alinamadi: %s", exc)

    @staticmethod
    def _captcha_denetle(metin: str) -> None:
        """Sunucu captcha istiyorsa isi durdurur.

        Bilerek COZULMUYOR. Bot denetimini atlatmak bu projenin sinirinin
        disinda; boyle bir durumda isi insan devralmali.
        """
        if CAPTCHA_BAYRAGI_RE.search(metin or ""):
            raise CaptchaAcik("Danistay captcha istedi; otomatik cekim durduruldu.")

    def _bekle(self) -> None:
        gecen = time.monotonic() - self._son_istek
        if gecen < self.delay:
            time.sleep(self.delay - gecen)
        self._son_istek = time.monotonic()

    def _cache_yolu(self, karar_id: str) -> Path:
        ad = hashlib.sha256(karar_id.encode()).hexdigest()[:20]
        return self.cache_dir / f"{ad}.json"

    # ---------- arama ----------
    def ara(self, kelime: str, *, en_fazla: int = 300,
            sayfa_boyu: int = 100) -> list[DanistayKarari]:
        """Bir anahtar kelime icin karar listesi doner (metin haric)."""
        govde = _bos_govde()
        # Deger tirnak icinde: site tam ifade aramasi icin boyle gonderiyor
        govde["andKelimeler"] = [f'"{kelime}"']

        self._bekle()
        try:
            baslat = self.session.post(BASLAT_UCU, json={"data": govde}, timeout=60)
            self._captcha_denetle(baslat.text)
        except requests.RequestException as exc:
            log.warning("arama baslatilamadi (%s): %s", kelime, exc)
            return []

        kayitlar: list[DanistayKarari] = []
        sayfa, toplam = 1, None
        while len(kayitlar) < en_fazla:
            self._bekle()
            istek = {"data": {**govde, "pageSize": sayfa_boyu, "pageNumber": sayfa}}
            try:
                cevap = self.session.post(ARAMA_UCU, json=istek, timeout=60)
                self._captcha_denetle(cevap.text)
                govde_cevap = cevap.json() or {}
                veri = govde_cevap.get("data")
                if veri is None:
                    # Hatayi GORUNUR yap: onceki surumde bu dal sessizdi ve
                    # anahtarlar sirayla "0 kayit" doneriyordu, sebebi
                    # gorunmuyordu.
                    mesaj = (govde_cevap.get("metadata") or {}).get("FMTE", "")
                    log.warning("liste bos (%s s.%d): %s", kelime, sayfa, mesaj[:90])
            except CaptchaAcik:
                raise
            except (requests.RequestException, ValueError) as exc:
                log.warning("liste hatasi (%s s.%d): %s", kelime, sayfa, exc)
                break
            if not veri:
                break

            if toplam is None:
                toplam = veri.get("recordsTotal") or 0
                log.info("Danistay '%s': %s karar", kelime, f"{toplam:,}")

            satirlar = veri.get("data") or []
            if not satirlar:
                break
            for r in satirlar:
                kayitlar.append(DanistayKarari(
                    id=str(r.get("id", "")),
                    daire=(r.get("daireKurul") or "").strip(),
                    esas_no=(r.get("esasNo") or "").strip(),
                    karar_no=(r.get("kararNo") or "").strip(),
                    karar_tarihi=(r.get("kararTarihi") or "").strip(),
                    anahtar=kelime,
                ))
            sayfa += 1
            if toplam and len(kayitlar) >= toplam:
                break
        return kayitlar[:en_fazla]

    # ---------- belge ----------
    def belge(self, karar_id: str, anahtar: str = "") -> str:
        """Kararin tam metnini doner. Onbellekteyse ag istegi yapilmaz."""
        onbellek = self._cache_yolu(karar_id)
        if onbellek.exists():
            return json.loads(onbellek.read_text(encoding="utf-8")).get("metin", "")

        ham = ""
        for _ in range(3):
            self._bekle()
            try:
                r = self.session.get(
                    BELGE_UCU,
                    params={"id": karar_id, "arananKelime": f'"{anahtar}"' if anahtar else ""},
                    timeout=60)
                r.raise_for_status()
                self._captcha_denetle(r.text)
                ham = r.text or ""
                if ham:
                    break
            except CaptchaAcik:
                raise
            except requests.RequestException as exc:
                log.debug("belge hatasi (%s): %s", karar_id, exc)
        if ham:
            onbellek.write_text(json.dumps({"metin": ham}, ensure_ascii=False),
                                encoding="utf-8")
        return ham
