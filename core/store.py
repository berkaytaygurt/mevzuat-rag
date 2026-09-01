"""Vektor + metadata deposu (Qdrant, gomulu mod -- sunucu gerekmez).

Metadata'yi vektorle birlikte tutmamizin sebebi hukuki filtreleme: "sadece
yururlukteki maddeler", "sadece Is Kanunu", "sadece bu bolum" gibi kisitlar
retrieval'dan ONCE uygulanabilsin. Mulga bir maddeyi guncelmis gibi sunmak
bu projedeki en tehlikeli hata turu.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

import config

log = logging.getLogger(__name__)

KOLEKSIYON = "mevzuat"


def _nokta_id(chunk_id: str) -> int:
    """chunk_id -> kararli sayisal id.

    Python'un yerlesik hash()'i string'ler icin surec basina rastgelelestirilir
    (PYTHONHASHSEED). Onunla uretilen id, ayni maddeye her calistirmada farkli
    bir deger verir: yeniden indeksleme kaydi guncellemek yerine kopyasini
    ekler. hashlib deterministiktir.
    """
    return int.from_bytes(hashlib.sha1(chunk_id.encode("utf-8")).digest()[:8],
                          "big") % (2 ** 63)


class MevzuatStore:
    def __init__(self, yol: Path | None = None, boyut: int = 1024):
        self.yol = yol or (config.INDEX_DIR / "qdrant")
        self.boyut = boyut
        self.client = QdrantClient(path=str(self.yol))
        self._hazirla()

    def _hazirla(self) -> None:
        mevcut = {c.name for c in self.client.get_collections().collections}
        if KOLEKSIYON not in mevcut:
            self.client.create_collection(
                collection_name=KOLEKSIYON,
                vectors_config=models.VectorParams(
                    size=self.boyut, distance=models.Distance.COSINE),
            )
            # Filtrelenecek alanlar icin indeks
            for alan, tip in [("mevzuat_no", "keyword"), ("mevzuat_tur", "keyword"),
                              ("madde_no", "keyword"), ("mulga", "bool")]:
                self.client.create_payload_index(
                    collection_name=KOLEKSIYON, field_name=alan, field_schema=tip)
            log.info("koleksiyon olusturuldu (boyut=%d)", self.boyut)

    def upsert(self, maddeler: list, vektorler: np.ndarray) -> None:
        if len(maddeler) != len(vektorler):
            raise ValueError(f"madde ({len(maddeler)}) ve vektor ({len(vektorler)}) sayisi farkli")

        noktalar = []
        for m, v in zip(maddeler, vektorler):
            d = m.to_dict() if hasattr(m, "to_dict") else dict(m)
            noktalar.append(models.PointStruct(
                id=_nokta_id(d["chunk_id"]),
                vector=v.tolist(),
                payload=d,
            ))
        for i in range(0, len(noktalar), 256):
            self.client.upsert(collection_name=KOLEKSIYON, points=noktalar[i:i + 256])
        log.info("%d madde yazildi", len(noktalar))

    def search(self, vektor: np.ndarray, limit: int = 10,
               mevzuat_no: str | None = None, mulga_haric: bool = True) -> list[dict]:
        kosullar = []
        if mevzuat_no:
            kosullar.append(models.FieldCondition(
                key="mevzuat_no", match=models.MatchValue(value=mevzuat_no)))
        if mulga_haric:
            kosullar.append(models.FieldCondition(
                key="mulga", match=models.MatchValue(value=False)))

        sonuc = self.client.query_points(
            collection_name=KOLEKSIYON,
            query=vektor.tolist(),
            limit=limit,
            query_filter=models.Filter(must=kosullar) if kosullar else None,
        ).points
        return [{**p.payload, "skor": p.score} for p in sonuc]

    def tum_kayitlar(self) -> list[dict]:
        """BM25 indeksi kurmak icin tum payload'lari doner."""
        cikti, offset = [], None
        while True:
            batch, offset = self.client.scroll(
                collection_name=KOLEKSIYON, limit=1000,
                offset=offset, with_payload=True, with_vectors=False)
            cikti.extend(p.payload for p in batch)
            if offset is None:
                break
        return cikti

    def sayi(self) -> int:
        return self.client.get_collection(KOLEKSIYON).points_count

    def close(self) -> None:
        self.client.close()
