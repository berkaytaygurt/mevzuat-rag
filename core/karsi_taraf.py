"""Karsi tarafin dayanabilecegi maddeleri arar.

FIKIR
Kullanici kendi sorusunu kendi tarafindan sorar ("isten cikarildim tazminat
alabilir miyim"). Sistem de o tarafin maddelerini getirir. Ama bir dosyada
karsi tarafin dayanacagi maddeler de vardir ve avukatin en cok zamanini
yiyen sey onlari dusunmektir.

Burada yapilan sey, sorunun KARSI TARAFIN GOZUNDEN yeniden kurulup ayrica
aranmasi. Ornek:

    kullanici : "isten cikarildim tazminat alabilir miyim"
    karsi     : "isverenin hakli nedenle fesih sebepleri"

NE YAPMIYOR -- bilerek
Tavsiye vermiyor, zayif nokta tespiti yapmiyor, sure hesabi yapmiyor,
"su argumani kullan" demiyor. Bunlar hukuki tavsiye olur ve sistemin
olculen dogrulugu (dogal dilde MRR 0.26) bunu tasimaz. Ayrica yanlis
madde numarasini kullanici acip gorebilir, yanlis stratejiyi ancak
durusmada anlar.

Yalnizca "bu maddeler de var, bunlara da bak" diyor. Cikarim avukatin.
"""
from __future__ import annotations

import logging

import config

log = logging.getLogger(__name__)

SISTEM = """Sen bir hukuk arama yardımcısısın. Sana bir kişinin kendi
tarafından yazdığı soru verilir. Sen bu uyuşmazlıkta KARŞI TARAFIN
dayanabileceği hukuki kavramları listelersin.

Kurallar:
1. Yalnızca arama terimleri yaz, cümle kurma, yorum yapma.
2. En fazla 8 terim, virgülle ayır.
3. Tavsiye verme, kimin haklı olduğunu söyleme.
4. Soru bir uyuşmazlık içermiyorsa "YOK" yaz."""

ISTEM = """Soru: {soru}

Bu uyuşmazlıkta karşı tarafın dayanabileceği hukuki kavramları yaz."""


def karsi_sorgu(soru: str, uretici) -> str:
    """Soruyu karsi tarafin gozunden arama terimlerine cevirir.

    Bos string doner: soru uyusmazlik icermiyorsa ya da uretim basarisizsa.
    """
    try:
        c = uretici._gemini(ISTEM.format(soru=soru), sistem=SISTEM,
                            model=config.GEMINI_HIZLI_MODEL)
    except Exception as exc:
        log.warning("karsi sorgu uretilemedi: %s", str(exc)[:80])
        return ""

    c = (c or "").strip().split("\n")[0]
    if not c or "YOK" in c.upper() or len(c) < 8:
        return ""
    return c


def karsi_maddeler(soru: str, retriever, uretici, limit: int = 5,
                   asil_maddeler: list[dict] | None = None) -> tuple[str, list[dict]]:
    """(karsi_sorgu, maddeler) doner.

    asil_maddeler verilirse, zaten gosterilen maddeler ayiklanir -- ayni
    maddeyi iki kez gostermek kullaniciyi yaniltir, "karsi taraf da buna
    dayaniyor" izlenimi verir.
    """
    sorgu = karsi_sorgu(soru, uretici)
    if not sorgu:
        return "", []

    gorulen = {m.get("chunk_id") for m in (asil_maddeler or [])}
    bulunan = retriever.ara(sorgu, limit=limit + len(gorulen))
    yeni = [m for m in bulunan if m.get("chunk_id") not in gorulen]
    return sorgu, yeni[:limit]
