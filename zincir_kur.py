"""Atif zincirini kurar: hangi karar hangi maddeyi yorumlamis.

Kararlarin METNI onbellekte, KUNYESI (daire, esas/karar no, tarih)
kararlar.json'da. Ikisi id uzerinden birlestirilir.

Yalnizca kulliyatta gercekten var olan maddeler indekslenir; metinden
cikarim bazen olmayan madde uretiyor ("4857 m.438" gibi) ve bunlar
kullaniciya olu baglanti olarak gorunur.

    .venv\\Scripts\\python zincir_kur.py
"""
from __future__ import annotations

import glob
import json
import logging

import config
from core import atif_zinciri

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("zincir")


def main() -> None:
    kunye: dict[str, dict] = {}
    kj = config.RAW_DIR / "kararlar.json"
    if kj.exists():
        for k in json.loads(kj.read_text(encoding="utf-8")):
            kunye[str(k.get("id"))] = k

    kararlar = []
    for f in sorted(glob.glob(str(config.RAW_DIR / "karar_cache" / "*.json"))):
        c = json.loads(open(f, encoding="utf-8").read())
        kid = str(c.get("id"))
        k = dict(kunye.get(kid, {}))
        k["id"], k["metin"] = kid, c.get("metin", "")
        kararlar.append(k)
    log.info("%d Yargitay karari, %d kunye", len(kararlar), len(kunye))

    # Danistay kararlari da zincire giriyor: 657, 2577 gibi kanunlari
    # yorumluyorlar ve idari yargi tarafi baska turlu bos kaliyor.
    # Kunye ve metin ayni dosyada duruyor, onbellege gitmeye gerek yok.
    dj = config.RAW_DIR / "danistay_kararlar.json"
    if dj.exists():
        danistay = json.loads(dj.read_text(encoding="utf-8"))
        kararlar += danistay
        log.info("%d Danistay karari eklendi", len(danistay))

    kayitlar = json.loads(
        (config.INDEX_DIR / "kayitlar.json").read_text(encoding="utf-8"))
    gecerli = atif_zinciri.gecerli_madde_kumesi(kayitlar)
    log.info("kulliyatta %d madde", len(gecerli))

    dizin = atif_zinciri.kur(kararlar, gecerli_maddeler=gecerli)
    atif_zinciri.kaydet(dizin)
    baglanti = sum(len(v) for v in dizin.values())
    log.info("atif zinciri: %d madde, %d baglanti", len(dizin), baglanti)


if __name__ == "__main__":
    main()
