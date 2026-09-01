"""Qdrant'taki vektorleri yeni depoya aktarir (yeniden gomme yapmadan)."""
import logging
import time

import numpy as np

from core.store import KOLEKSIYON, MevzuatStore
from core.vektor import VektorDeposu

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("aktar")


def main() -> None:
    store = MevzuatStore()
    toplam = store.sayi()
    log.info("Qdrant'ta %d kayit var, aktariliyor...", toplam)

    kayitlar: list[dict] = []
    vektorler: list[list[float]] = []
    offset = None
    basla = time.time()

    while True:
        batch, offset = store.client.scroll(
            collection_name=KOLEKSIYON, limit=2000, offset=offset,
            with_payload=True, with_vectors=True)
        for p in batch:
            kayitlar.append(p.payload)
            vektorler.append(p.vector)
        if len(kayitlar) % 20000 < 2000:
            log.info("  %d / %d", len(kayitlar), toplam)
        if offset is None:
            break

    store.close()
    log.info("okuma bitti: %d kayit, %.0f sn", len(kayitlar), time.time() - basla)

    dizi = np.asarray(vektorler, dtype=np.float32)
    # Kosinus benzerligini tek matris carpimiyla yapabilmek icin normalize
    norm = np.linalg.norm(dizi, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    dizi /= norm

    VektorDeposu().kaydet(kayitlar, dizi)
    log.info("aktarim tamam: %s", dizi.shape)


if __name__ == "__main__":
    main()
