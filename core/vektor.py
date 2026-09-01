"""Vektor deposu: bellekte matris, arama matris carpimi.

Neden Qdrant'tan vazgecildi: gomulu (local) modda indeks kurmuyor, her sorguda
tum noktalari tek tek geziyor. 33 bin maddede sorun degildi; 174 binde sorgu
basina 2.97 saniye tutuyordu ve toplam aramanin %87'siydi. Kutuphane bunu
zaten uyariyor ("Local mode is not recommended for collections with more than
20,000 points").

Olculdu (173.907 x 1024):

    Qdrant gomulu     2970 ms
    numpy (CPU)         36 ms
    torch (GPU)         34 ms

Vektorler normalize edildigi icin kosinus benzerligi = ic carpim; yani tek bir
matris carpimi yeterli. 174 bin vektor float32 olarak 0.71 GB, bellekte rahat
durur. Metadata filtresi (mulga haric) maske ile uygulanir.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

import config

log = logging.getLogger(__name__)

VEKTOR_DOSYASI = "vektorler.npy"
KAYIT_DOSYASI = "kayitlar.json"


class VektorDeposu:
    def __init__(self, yol: Path | None = None):
        self.yol = yol or config.INDEX_DIR
        self._vektorler: np.ndarray | None = None
        self._kayitlar: list[dict] | None = None
        self._mulga_maskesi: np.ndarray | None = None

    # ---------- kurulum ----------
    def kaydet(self, kayitlar: list[dict], vektorler: np.ndarray) -> None:
        if len(kayitlar) != len(vektorler):
            raise ValueError(
                f"kayit ({len(kayitlar)}) ve vektor ({len(vektorler)}) sayisi farkli")
        self.yol.mkdir(parents=True, exist_ok=True)
        np.save(self.yol / VEKTOR_DOSYASI, vektorler.astype(np.float32))
        (self.yol / KAYIT_DOSYASI).write_text(
            json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")
        self._vektorler, self._kayitlar, self._mulga_maskesi = None, None, None
        log.info("vektor deposu yazildi: %d kayit", len(kayitlar))

    # ---------- yukleme ----------
    def _yukle(self) -> None:
        if self._vektorler is not None:
            return
        vyol, kyol = self.yol / VEKTOR_DOSYASI, self.yol / KAYIT_DOSYASI
        if not (vyol.exists() and kyol.exists()):
            raise FileNotFoundError(
                f"Vektor deposu bulunamadi ({vyol.name}). "
                "Once 'python cli.py indeksle' calistirin.")
        # Tamamen bellege aliyoruz. mmap ile denendi: her sorguda diskten
        # okundugu icin arama 36 ms yerine ~270 ms suruyordu. 0.71 GB RAM,
        # kazanilan hizin yaninda ucuz.
        self._vektorler = np.load(vyol)
        self._kayitlar = json.loads(kyol.read_text(encoding="utf-8"))
        self._mulga_maskesi = np.array(
            [bool(k.get("mulga")) for k in self._kayitlar], dtype=bool)
        log.info("vektor deposu yuklendi: %d kayit", len(self._kayitlar))

    @property
    def kayitlar(self) -> list[dict]:
        self._yukle()
        return self._kayitlar

    def sayi(self) -> int:
        self._yukle()
        return len(self._kayitlar)

    # ---------- arama ----------
    def search(self, vektor: np.ndarray, limit: int = 10,
               mevzuat_no: str | None = None,
               mulga_haric: bool = True) -> list[dict]:
        self._yukle()
        q = np.asarray(vektor, dtype=np.float32).ravel()
        skorlar = self._vektorler @ q            # kosinus (vektorler normalize)

        if mulga_haric or mevzuat_no:
            # Elenen kayitlari -inf yaparak siralamanin disinda birakiyoruz;
            # dizi kopyalamaktan (0.7 GB) ucuz.
            skorlar = np.array(skorlar, copy=True)
            if mulga_haric:
                skorlar[self._mulga_maskesi] = -np.inf
            if mevzuat_no:
                uy = np.fromiter(
                    (k.get("mevzuat_no") == mevzuat_no for k in self._kayitlar),
                    dtype=bool, count=len(self._kayitlar))
                skorlar[~uy] = -np.inf

        n = min(limit, len(skorlar))
        # argpartition: tam siralama O(n log n), bize yalnizca ilk n lazim
        aday = np.argpartition(-skorlar, n - 1)[:n]
        aday = aday[np.argsort(-skorlar[aday])]
        return [{**self._kayitlar[i], "skor": float(skorlar[i])}
                for i in aday if np.isfinite(skorlar[i])]

    def tum_kayitlar(self) -> list[dict]:
        """BM25 indeksi kurmak icin tum kayitlari doner."""
        return self.kayitlar

    def close(self) -> None:
        self._vektorler = None
        self._kayitlar = None
        self._mulga_maskesi = None
