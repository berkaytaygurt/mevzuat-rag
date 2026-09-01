"""Sorgu genisletme.

Kullanici gundelik dille yazar ("isten atildim param ne olur"); kanun metni
hukuk diliyle yazilmistir ("kidem tazminati", "is sozlesmesinin feshi"). Ikisi
ayni seyi anlatir ama kelimeleri ortusmez ve hem BM25 hem embedding bu
ortusmeden beslenir.

Bu modul, sorguyu aramadan once LLM'e verip hukuk terimleriyle zenginlestirir.
Orijinal sorgu korunur ve genisletilmis hali ona EKLENIR -- degistirilmez:
LLM yanlis yone saparsa asil sorgunun sinyali kaybolmasin.

Maliyeti her aramaya bir LLM cagrisi. Faydasi olculmeden acilmamali.
"""
from __future__ import annotations

import logging
import re

import config

log = logging.getLogger(__name__)

# Genisletme, cevap uretmekten farkli bir is. Cevap ureticisinin sistem
# promptu "mevzuat yoksa reddet" diyor; o promptla cagrildiginda yerel model
# genisletme yerine "Verilen mevzuatta bu soruya dayanak bulamadim" yaziyordu.
SISTEM = """Sen bir arama terimi uretecisin. Sana verilen soruyu, Türk
mevzuatında arama yapmak için kullanılacak hukuk terimlerine çevirirsin.
Soruyu cevaplamazsın, açıklama yapmazsın, yalnızca terim listesi yazarsın."""

ISTEM = """Aşağıdaki soruyu, Türk mevzuatında arama yapmak için hukuk
terimleriyle zenginleştir.

Kurallar:
- Yalnızca terimleri yaz, cümle kurma
- En fazla 8 terim
- Virgülle ayır
- Soruyu cevaplama, sadece arama terimleri üret
- Kanun adı biliyorsan ekle

Soru: {soru}

Terimler:"""


def _temizle(cikti: str) -> str:
    cikti = re.sub(r"^\s*(terimler|cevap)\s*:\s*", "", cikti.strip(), flags=re.I)
    cikti = cikti.split("\n")[0]
    parcalar = [p.strip(" .;") for p in cikti.split(",")]
    return ", ".join(p for p in parcalar if 2 < len(p) < 60)[:300]


class SorguGenisletici:
    def __init__(self, provider: str | None = None):
        self.provider = provider or config.GENISLET_PROVIDER
        self._uretici = None

    @property
    def uretici(self):
        if self._uretici is None:
            from .generate import Generator

            self._uretici = Generator(provider=self.provider)
        return self._uretici

    def genislet(self, soru: str) -> str:
        """Sorguyu hukuk terimleriyle zenginlestirir.

        Basarisiz olursa orijinal sorgu doner: arama, LLM'e bagimli hale
        gelmemeli.
        """
        if not config.SORGU_GENISLET:
            return soru
        try:
            istem = ISTEM.format(soru=soru)
            # Kucuk is: hizli model yeter. Buyuk model bu istegi 36
            # saniyede donduruyordu, flash-lite 0.6 saniyede.
            ek = (self.uretici._gemini(istem, sistem=SISTEM,
                                       model=config.GEMINI_HIZLI_MODEL)
                  if self.provider == "gemini"
                  else self.uretici._local(istem, sistem=SISTEM, max_token=120))
        except Exception as exc:
            log.warning("sorgu genisletilemedi: %s", str(exc)[:80])
            return soru

        ek = _temizle(ek or "")
        if not ek:
            return soru
        log.debug("sorgu genisletildi: %r + %r", soru, ek)
        return f"{soru} {ek}"
