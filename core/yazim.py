"""Turkce karakter kullanilmadan yazilan sorgulari duzeltir.

Kullanicilarin cogu sorgusunu "hirsizlik sucunun cezasi" diye yazar; kanun
metninde ise "hırsızlık suçunun cezası" gecer. Bilgisayar icin bunlar farkli
kelimeler ve olculen kayip ciddi: ASCII yazimda MRR 0.753'ten 0.645'e dusuyor,
"evlenme yasi kac" gibi bazi sorularda dogru madde ilk bese hic giremiyor.

Cozum, sozlugu kulliyatin kendisinden cikarmak: her kelimenin ASCII'ye
katlanmis hali anahtar, metinde en sik gecen gercek yazimi deger olur.
Boylece sozluk tam da bu alanin kelimelerini tanir ve disaridan bir servise
veya ek bir model cagrisina gerek kalmaz.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

import config

from .retrieve import _tr_katla

log = logging.getLogger(__name__)

KELIME_RE = re.compile(r"\w+", re.UNICODE)
# Cok kisa kelimeler ("ve", "bir") ayirt edici degil, sozluge alinmaz
EN_KISA = 3


def kucult(kelime: str) -> str:
    """Turkceye uygun kucultme.

    Python'un lower()'i Turkce "İ" harfini "i" + U+0307 (birlesik nokta)
    diye ikiye ayiriyor. Kanun metinleri basliklari BUYUK harfle yazdigi
    icin sozluge bu bozuk bicim giriyordu ve duzeltici sorguya gorunmez bir
    karakter sokuyordu: "türk medeni kanunu" -> "türk medeni\\u0307 kanunu".
    Sonra vektor ve cross-encoder bunu baska bir kelime sayiyordu.

    Olculdu: sozlukteki 106.559 kelimenin 2.411'i (%2,3) bu bozuk bicimdeydi
    -- "yönetmeliği", "tebliği", "ithalatta" gibi cok gecenler dahil.
    """
    return kelime.replace("İ", "i").replace("I", "ı").lower()


def sozluk_kur(maddeler: list[dict], yol: Path | None = None) -> dict[str, str]:
    """Maddelerden ASCII -> gercek yazim sozlugu uretir ve diske yazar."""
    sayac: dict[str, Counter] = defaultdict(Counter)
    for m in maddeler:
        metin = f"{m.get('mevzuat_adi', '')} {m.get('baslik', '')} {m.get('metin', '')}"
        for kelime in KELIME_RE.findall(metin):
            if len(kelime) >= EN_KISA:
                sayac[_tr_katla(kelime)][kucult(kelime)] += 1

    # Yalnizca aksanli bir karsiligi olanlari sakla: "tazminat" gibi zaten
    # ASCII olan kelimeler icin kayit tutmak sozlugu gereksiz buyutur.
    sozluk = {}
    for ascii_bicim, sayimlar in sayac.items():
        en_sik = sayimlar.most_common(1)[0][0]
        if en_sik != ascii_bicim:
            sozluk[ascii_bicim] = en_sik

    yol = yol or (config.INDEX_DIR / "yazim.json")
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(sozluk, ensure_ascii=False), encoding="utf-8")
    log.info("yazim sozlugu kuruldu: %d kelime -> %s", len(sozluk), yol.name)
    return sozluk


class YazimDuzeltici:
    def __init__(self, yol: Path | None = None):
        self.yol = yol or (config.INDEX_DIR / "yazim.json")
        self._sozluk: dict[str, str] | None = None

    @property
    def sozluk(self) -> dict[str, str]:
        if self._sozluk is None:
            if self.yol.exists():
                self._sozluk = json.loads(self.yol.read_text(encoding="utf-8"))
            else:
                log.warning("yazim sozlugu yok (%s); duzeltme yapilmayacak", self.yol)
                self._sozluk = {}
        return self._sozluk

    def duzelt(self, soru: str) -> str:
        """Sorguda aksansiz yazilmis kelimeleri gercek yazimlariyla degistirir.

        Zaten Turkce karakter iceren kelimelere dokunmaz: kullanici dogru
        yazmissa onun yazimi sozlugun tahmininden daha guveniliridir.
        """
        if not self.sozluk:
            return soru

        def degistir(m: re.Match) -> str:
            kelime = m.group(0)
            if len(kelime) < EN_KISA:
                return kelime
            # Kelimede Turkce'ye ozgu harf varsa kullanici bilerek yazmistir
            if any(h in kelime for h in "çğıöşüÇĞİÖŞÜ"):
                return kelime
            karsilik = self.sozluk.get(_tr_katla(kelime))
            if not karsilik:
                return kelime
            return karsilik.upper() if kelime.isupper() else karsilik

        return KELIME_RE.sub(degistir, soru)
