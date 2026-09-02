"""Madde metninde soruyla en ilgili fikrayi isaretler.

NEDEN
Getirilen maddeler ortalama 800 karakter; bes madde okumak dakikalar aliyor.
Oysa cogu soruda cevap tek bir fikrada. Bu modul metni fikralara bolup her
birini sorguyla karsilastiriyor ve en yakinini isaretliyor.

Tavsiye vermiyor, yorum yapmiyor -- yalnizca "bu kisim sorunuzla ilgili
gorunuyor" diyor. Ctrl+F'in anlamsal hali.

EMIN DEGILSE ISARETLEMIYOR
Yanlis fikrayi isaretlemek, hic isaretlememekten kotu: kullanici isaretli
yeri okuyup dogru fikrayi atlar. Bu yuzden en iyi fikra ikincisinden
belirgin sekilde iyi degilse (MARJ) hicbir sey isaretlenmiyor.
"""
from __future__ import annotations

import logging
import re

import numpy as np

log = logging.getLogger(__name__)

# Mevzuat metinlerinde fikra isareti YOK: ayristirici govdeyi bosluklarla
# birlestirdigi icin satir sonu da "(1)" gibi bir isaret de kalmiyor
# (olculdu -- Is Kanunu m.53, 1018 karakter, sifir satir sonu). Bu yuzden
# bolme CUMLE sinirindan yapiliyor.
#
# Kisaltmalarda bolmemek icin nokta sonrasi BUYUK harf araniyor; "m.53",
# "md.", "sayili" gibi yerlerde bolunmuyor.
CUMLE_SONU = re.compile(r"(?<=[.:;])\s+(?=[A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dc])")

# Isaretlenecek parcanin hedef uzunlugu. Tek cumle cogu zaman cok kisa ve
# baglamsiz kaliyor; komsu cumlelerle birlestirip ~220 karaktere getiriyoruz.
HEDEF_UZUNLUK = 220

# Isaretlenmeye deger en kisa parca
EN_AZ_UZUNLUK = 60

# En iyi parca, ikincisinden en az bu kadar iyi olmali. Altindaysa hicbir
# sey isaretlenmiyor: yanlis yeri isaretlemek, hic isaretlememekten kotu
# cunku kullanici isaretli yeri okuyup dogru kismi atlar.
MARJ = 0.03


def fikralara_bol(metin: str) -> list[str]:
    """Madde metnini cumle gruplarina boler.

    Once cumlelere ayirir, sonra HEDEF_UZUNLUK'a yakin gruplar halinde
    birlestirir: tek cumle baglamsiz kaliyor, tum metin ise isaretlemeyi
    anlamsiz kiliyor.
    """
    if not metin or not metin.strip():
        return []
    cumleler = [c.strip() for c in CUMLE_SONU.split(metin.strip()) if c.strip()]
    if not cumleler:
        return [metin.strip()]

    gruplar: list[str] = []
    tampon = ""
    for c in cumleler:
        if tampon and len(tampon) + len(c) + 1 > HEDEF_UZUNLUK:
            gruplar.append(tampon)
            tampon = c
        else:
            tampon = f"{tampon} {c}" if tampon else c
    if tampon:
        gruplar.append(tampon)

    # Son grup cok kisaysa oncekine yapistir.
    # Tek satirda yazilamaz: "gruplar[-2] = gruplar[-2] + gruplar.pop()"
    # once pop yapip listeyi bire dusuruyor, sonra [-2] IndexError veriyor.
    if len(gruplar) > 1 and len(gruplar[-1]) < EN_AZ_UZUNLUK:
        son = gruplar.pop()
        gruplar[-1] = gruplar[-1] + " " + son
    return gruplar


def vurgulanacak(metin: str, soru: str, reranker) -> int:
    """Isaretlenecek parcanin sirasini doner; emin degilse -1.

    CROSS-ENCODER kullaniyor, gomme benzerligi DEGIL. Olculdu (10 soru):
    gomme ile isaretledigi yerlerin yalnizca %60'i dogruydu ve esigi
    sikilastirmak duzeltmiyordu (0.10 marjda tek isaret kaliyor, o da
    yanlis). Sebep: bir maddenin icindeki cumleler zaten ayni konuda,
    vektorleri birbirine cok yakin ve ayirt edemiyor. Cross-encoder
    soru ile metni birlikte okudugu icin ince ayrimda cok daha iyi.
    """
    fikralar = fikralara_bol(metin)
    if len(fikralar) < 2:
        return -1

    try:
        adaylar = [{"metin": f, "baslik": "", "mevzuat_adi": ""} for f in fikralar]
        sirali = reranker.sirala(soru, adaylar, limit=len(adaylar))
    except Exception as exc:
        log.debug("fikra siralamasi basarisiz: %s", exc)
        return -1
    if len(sirali) < 2:
        return -1

    en_iyi_metin = sirali[0].get("metin", "")
    fark = sirali[0].get("skor", 0) - sirali[1].get("skor", 0)
    if fark < MARJ or len(en_iyi_metin) < EN_AZ_UZUNLUK:
        return -1
    try:
        return fikralar.index(en_iyi_metin)
    except ValueError:
        return -1


def parcalari_hazirla(metin: str, soru: str, reranker) -> list[dict]:
    """Fikralari ve hangisinin isaretlenecegini doner.

    Arayuz bu listeyi oldugu gibi cizer; metin icinde dizgi arama yapmaz
    (dizgi eslestirme kirilgan: metinde tekrar eden ifadeler var).
    """
    fikralar = fikralara_bol(metin)
    if not fikralar:
        return []
    sira = vurgulanacak(metin, soru, reranker) if len(fikralar) > 1 else -1
    return [{"metin": f, "vurgu": i == sira} for i, f in enumerate(fikralar)]
