"""mevzuat.gov.tr icin nazik HTTP istemcisi.

- Eksik gonderilen ara sertifikayi kendi CA bundle'imizla tamamlar (verify=False YOK).
- Istekler arasinda bekler, hata durumunda ustel geri cekilme uygular.
- Indirdigini diske cacheler; ayni sayfa iki kez cekilmez.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

import config

log = logging.getLogger(__name__)

# meta charset "Windows-1254" diyor ama govde gercekte UTF-8.
# Once UTF-8 deneriz, tutmazsa cp1254'e duseriz.
_ENCODINGS = ("utf-8", "windows-1254")


def decode(raw: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class MevzuatClient:
    def __init__(self, delay: float | None = None, cache_dir: Path | None = None):
        self.delay = config.SCRAPE_DELAY if delay is None else delay
        self.cache_dir = cache_dir or (config.RAW_DIR / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9",
        })
        self.session.verify = str(config.CERT_BUNDLE)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:20]}.html"

    def get(self, url: str, *, use_cache: bool = True, retries: int = 3) -> str:
        cached = self._cache_path(url)
        if use_cache and cached.exists():
            return decode(cached.read_bytes())

        last_error: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=45)
                resp.raise_for_status()
                cached.write_bytes(resp.content)
                return decode(resp.content)
            except requests.RequestException as exc:
                last_error = exc
                wait = self.delay * (2 ** attempt)
                log.warning("istek basarisiz (%d/%d) %s -> %s; %.1fs bekleniyor",
                            attempt + 1, retries, url, exc, wait)
                time.sleep(wait)

        raise RuntimeError(f"{retries} denemede alinamadi: {url}") from last_error

    def get_bytes(self, url: str, *, use_cache: bool = True, retries: int = 3) -> bytes:
        """Ikili icerik (PDF) icin. Metin cozumlemesi yapmaz."""
        cached = self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:20]}.bin"
        if use_cache and cached.exists():
            return cached.read_bytes()

        last_error: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=120)
                resp.raise_for_status()
                cached.write_bytes(resp.content)
                return resp.content
            except requests.RequestException as exc:
                last_error = exc
                wait = self.delay * (2 ** attempt)
                log.warning("indirme basarisiz (%d/%d) %s -> %s", attempt + 1, retries, url, exc)
                time.sleep(wait)
        raise RuntimeError(f"{retries} denemede alinamadi: {url}") from last_error

    # Belge alinamadiginda sunucu 404 vermiyor; her seferinde ayni sahte
    # PDF'lerden birini donduruyor. Uc tanesi olculdu:
    #
    #     60.487  "belge bulunamadi"
    #     64.854  bos PDF (metin katmani hic yok)
    #    259.488  "T.C. CUMHURBASKANLIGI / Sayfada Calisma Yapilmaktadir"
    #
    # Sonuncusu tehlikeli: 10.832 karakter metin tasiyor, yani "icerik var"
    # gibi gorunuyor. Duz metin yedegi bunu gercek belge sanip indekse 68
    # cop kayit sokmustu.
    BOS_PDF_BOYUTU = 60487
    SAHTE_PDF_BOYUTLARI = frozenset({60487, 64854, 259488})
    # Boyut degisirse yakalayan ikinci savunma
    BAKIM_ISARETI = "Sayfada Çalışma Yapılmaktadır"

    # PDF'ler tur'e gore farkli dizinde duruyor. Olculdu (her turden bir
    # ornek indirilerek): kanun/tuzuk/kararname/yonetmelik dogrudan
    # /MevzuatMetin/ altinda; teblig ile kurum ve cumhurbaskanligi
    # yonetmelikleri /MevzuatMetin/yonetmelik/ altinda. Alt dizini atlamak
    # bu uc turde 4.099 belgenin bos PDF donmesine yol aciyordu.
    PDF_DIZINLERI = {7: "yonetmelik/", 8: "yonetmelik/", 9: "yonetmelik/"}

    def mevzuat_pdf(self, tur: int, no: int | str, tertip: int,
                    pdf_url: str = "") -> bytes:
        """Mevzuatin PDF metnini indirir.

        Katalog API'si pdfUrl alanini artik bos donduruyor, bu yuzden adres
        {dizin}{tur}.{tertip}.{no}.pdf kalibiyla kuruluyor. Bos PDF gelirse
        bilinen dizinler sirayla denenir; hicbiri tutmazsa bos bayt doner ve
        cagiran taraf HTML'e duser.
        """
        if pdf_url:
            return self.get_bytes(pdf_url)

        denenecek = [self.PDF_DIZINLERI.get(tur, "")]
        for d in ("", "yonetmelik/"):        # kalip degisirse yedek
            if d not in denenecek:
                denenecek.append(d)

        for dizin in denenecek:
            url = f"{config.BASE_URL}/MevzuatMetin/{dizin}{tur}.{tertip}.{no}.pdf"
            try:
                ham = self.get_bytes(url)
            except Exception:
                continue
            if len(ham) not in self.SAHTE_PDF_BOYUTLARI and len(ham) > 2000:
                return ham
        return b""

    def mevzuat_html(self, tur: int, no: int | str, tertip: int) -> str:
        """Bir mevzuatin tam metnini iceren iframe HTML'ini dondurur."""
        url = (f"{config.BASE_URL}/anasayfa/MevzuatFihristDetayIframe"
               f"?MevzuatTur={tur}&MevzuatNo={no}&MevzuatTertip={tertip}")
        return self.get(url)
