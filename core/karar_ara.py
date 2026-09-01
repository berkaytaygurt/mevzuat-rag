"""Mahkeme kararlarinda arama.

Kanun indeksinden AYRI tutuluyor. Sebep: ikisi tek indekste birlestirilirse
"yillik izin kac gun" gibi bir soruda kararlar maddeleri sirdan itebiliyor --
kararlar daha uzun ve konuyu daha cok kez tekrarliyor, bu da BM25 ve kosinus
skorlarini yukseltiyor. Kullanicinin once dayanak maddeyi gormesi gerekiyor.

Ayri indeks ayrica calisan sistemi riske atmiyor: kararlar indekslenmemis ya
da bozuk olsa bile mevzuat aramasi etkilenmiyor.
"""
from __future__ import annotations

import logging
from pathlib import Path

import config
from core.vektor import VektorDeposu

log = logging.getLogger(__name__)

KARAR_INDEX_DIR = config.ROOT / "data" / "index_karar"


class KararArayici:
    """Kararlarda anlamsal arama. Reranker varsa sonuclari yeniden siralar."""

    def __init__(self, embedder, yol: Path | None = None, reranker=None):
        self.embedder = embedder
        self.store = VektorDeposu(yol or KARAR_INDEX_DIR)
        self._reranker = reranker

    def hazir_mi(self) -> bool:
        try:
            return self.store.sayi() > 0
        except FileNotFoundError:
            return False

    def ara(self, soru: str, limit: int = 3, aday: int = 20) -> list[dict]:
        """Soruya en yakin karar parcalarini doner.

        Ayni karardan birden fazla parca gelebiliyor; kullaniciya ayni karari
        iki kez gostermemek icin karar_id basina en iyi parca tutuluyor.
        """
        if not self.hazir_mi():
            return []

        vektor = self.embedder.encode_query(soru)
        # mulga filtresi kararlarda anlamsiz (kayitlarda o alan yok)
        ham = self.store.search(vektor, limit=aday, mulga_haric=False)

        if self._reranker is not None and ham:
            ham = self._reranker.sirala(soru, ham, limit=aday)

        gorulen: set[str] = set()
        sonuc: list[dict] = []
        for k in ham:
            kid = k.get("karar_id") or k.get("chunk_id", "")
            if kid in gorulen:
                continue
            gorulen.add(kid)
            sonuc.append(k)
            if len(sonuc) >= limit:
                break
        return sonuc
