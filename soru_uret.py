"""Olcum seti icin sentetik soru uretir.

Nasil calisir: kulliyattan rastgele maddeler secilir, her biri Gemini'ye
verilir ve "bu maddenin cevabi olacagi bir soru yaz" denir. Sorunun dogru
cevabi, uretildigi maddedir.

SINIRI: Maddeden uretilen soru, o maddenin kelimelerini kullanma egiliminde
oldugu icin arama yapay olarak kolaylasir. Gercek kullanici "isten atildim
param ne olur" der, kanun "kidem tazminati" der. Bu yuzden modele acikca
"gunluk dille sor, kanun terimlerini kullanma" talimati veriliyor -- yine de
bu set gercek sorulardan daha iyimser sonuc verir.

Ikinci sinir: uretildigi madde "tek dogru cevap" sayiliyor. Ayni soruya cevap
verebilecek baska bir madde varsa yanlis sayilir. Yani olculen deger mutlak
dogruluk degil, degisikliklerin KARSILASTIRILMASI icin bir olcek.

    .venv\\Scripts\\python soru_uret.py --adet 200
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time

import config
from core.generate import Generator

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("soru")

CIKTI = config.ROOT / "tests" / "olcum_sentetik.py"

SISTEM = """Sen bir test verisi hazırlayıcısın. Sana bir mevzuat maddesi
verilir, sen o maddenin cevabı olacağı BİR soru yazarsın.

Kurallar:
1. Soruyu sıradan bir vatandaşın soracağı gibi, günlük dille yaz.
2. Kanun adını, madde numarasını ve maddedeki hukuk terimlerini KULLANMA.
   Kişi bu maddeyi bilmiyor, sadece derdini anlatıyor.
3. Tek cümle, en fazla 12 kelime.
4. Yalnızca soruyu yaz. Açıklama, tırnak, numara ekleme."""

ISTEM = """Madde:
{metin}

Bu maddenin cevabı olacağı bir soru yaz."""


def uygun_mu(m: dict) -> bool:
    """Soru uretmeye elverisli madde mi?"""
    metin = m.get("metin", "")
    if not (200 < len(metin) < 2500):
        return False
    if m.get("mulga") or not m.get("baslik"):
        return False
    # Yururluk/yurutme maddeleri ve degisiklik hukumleri soru uretmeye elverisli degil
    baslik = m["baslik"].lower()
    return not any(k in baslik for k in ("yürürlük", "yürütme", "değiştir", "kaldır"))


# Uretilen metnin soru olup olmadigini denetleyen kaliplar. Kucuk modeller
# soru yazmak yerine madde metnini kopyalayabiliyor ya da "Iste soru:" gibi
# meta metin uretebiliyor. Bunlar test setine girerse olcum bozulur.
_TARIH_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}|sayılı", re.IGNORECASE)
# Aksanli ve ASCII yazimlarin ikisi de yakalanmali: modelin ciktisi
# tutarsiz olabiliyor.
# Meta onek tespiti. Desen yerine basit bir kural kullaniyoruz: "Iste soru:",
# "Cevap:", "Madde:" gibi onekler metnin BASINDA iki nokta tasir. Duzenli
# ifadeyle yakalamak iki nedenle zordu -- onek iki kelimeli olabiliyor
# ("Iste soru:") ve Turkce'de "I" kucuk harfe "i" olmuyor, bu yuzden
# IGNORECASE "Iste" ile "iste"yi eslestiremiyor.
def _meta_onek_var_mi(soru: str) -> bool:
    bas = soru[:28]
    return ":" in bas and not bas.strip().endswith(":")


def soru_gecerli_mi(soru: str) -> bool:
    """Uretilen metnin kullanilabilir bir soru olup olmadigini soyler."""
    if not (12 < len(soru) < 120):
        return False
    if not soru.rstrip().endswith("?"):
        return False
    if _TARIH_RE.search(soru):          # madde metnini kopyalamis
        return False
    if _meta_onek_var_mi(soru):         # "Iste soru:" gibi meta cikti
        return False
    return 3 <= len(soru.split()) <= 16


def temizle(soru: str) -> str:
    # Yalnizca liste isaretlerini at ("1.", "- ", "* ", tirnak). Bastaki
    # rakamlari topluca silmek "2024 yilinda harclar..." gibi mesru soru
    # baslangicini bozuyordu.
    soru = re.sub(r'^\s*(?:\d{1,2}[.)]\s+|[-–—•*]\s*|["\']+)', "", soru.strip())
    soru = soru.split("\n")[0].strip(' "\'')
    return soru


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=200)
    ap.add_argument("--tohum", type=int, default=42)
    ap.add_argument("--saglayici", default=None,
                    help="gemini | local (varsayilan: .env'deki)")
    ap.add_argument("--bekleme", type=float, default=0.0,
                    help="istekler arasi bekleme (Gemini kotasi icin)")
    args = ap.parse_args()

    maddeler = json.loads(
        (config.RAW_DIR / "maddeler.json").read_text(encoding="utf-8"))
    havuz = [m for m in maddeler if uygun_mu(m)]
    log.info("%d maddeden %d tanesi soru uretmeye uygun", len(maddeler), len(havuz))

    random.seed(args.tohum)
    secilen = random.sample(havuz, min(args.adet, len(havuz)))

    uretici = Generator(provider=args.saglayici)
    sorular: list[tuple[str, str, str]] = []
    elenen = 0
    basla = time.time()

    for i, m in enumerate(secilen, 1):
        if args.bekleme:
            time.sleep(args.bekleme)
        try:
            istem = ISTEM.format(metin=m["metin"][:1800])
            ham = (uretici._gemini(istem, sistem=SISTEM)
                   if uretici.provider == "gemini"
                   else uretici._local(istem, sistem=SISTEM, max_token=60))
        except Exception as exc:
            log.warning("[%d] uretilemedi: %s", i, str(exc)[:60])
            continue

        soru = temizle(ham or "")
        if not soru_gecerli_mi(soru):
            elenen += 1
            continue
        sorular.append((soru, m["mevzuat_no"], m["madde_no"]))

        if i % 20 == 0:
            gecen = time.time() - basla
            log.info("%d gecerli / %d denendi (%d elendi, %.0f sn, kalan ~%.0f dk)",
                     len(sorular), i, elenen, gecen,
                     (len(secilen) - i) * gecen / i / 60)
            _yaz(sorular)

    _yaz(sorular)
    log.info("toplam %d soru -> %s", len(sorular), CIKTI.name)


def _yaz(sorular: list[tuple[str, str, str]]) -> None:
    satirlar = ",\n".join(
        f'    ({s!r}, {k!r}, {m!r})' for s, k, m in sorular)
    CIKTI.write_text(
        '"""Sentetik olcum seti -- soru_uret.py tarafindan uretildi.\n\n'
        "Her soru, karsisindaki maddeden uretildi; dogru cevap o maddedir.\n"
        "Sentetik oldugu icin gercek kullanici sorularindan daha iyimser sonuc\n"
        "verir; mutlak dogruluk olcusu degil, degisiklikleri karsilastirma\n"
        'olcegidir.\n"""\n\n'
        "SORULAR: list[tuple[str, str, str | None]] = [\n"
        + satirlar + "\n]\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
