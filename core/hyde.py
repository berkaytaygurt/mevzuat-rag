"""HyDE: soruyu once kanun diline cevirip oyle aramak.

OLCULEN SORUN
Soru ile cevabin dili farkli. Kullanici "isten cikarildim tazminat alir
miyim" diye soruyor; kanun "isveren, is sozlesmesini feshederken ..."
diye yaziyor. Soruyu dogrudan gommek iki farkli dil arasinda benzerlik
aramak demek.

COZUM
Modelden once SORUYU CEVAPLAYAN varsayimsal bir hukum metni yazmasi
isteniyor, arama o metinle yapiliyor. Yani soru cevabin diline
cevriliyor.

OLCULDU (34 soruluk set):

    ham sorgu                     1. sirada 23/34   MRR 0,734   1,6 sn
    uzun HyDE (4 cumle, 550 kar.) 1. sirada 24/34   MRR 0,819  12,1 sn
    KISA HyDE (1 cumle, 154 kar.) 1. sirada 32/34   MRR 0,956   4,7 sn

UZUNLUK ONEMLI. Uzun metin hem BM25'i yavaslatiyor (550 karakter ~80
arama terimi demek ve BM25 275 bin belgeyi o kadar terimle tariyor;
olculdu, arama 3,8 saniyeden 10,7 saniyeye cikiyor) hem de gurultu
ekleyip isabeti dusuruyor. Tek cumle hem daha hizli hem daha isabetli.

SINIRI
Uretilen metin UYDURMA bir hukumdur ve kullaniciya ASLA gosterilmez;
yalnizca arama sorgusu olarak kullanilir. Cevap yine kulliyattan gelen
gercek madde metinlerinden uretilir.

Madde numarasiyla yapilan aramalarda ("TBK 344") devreye girmez: orada
sorunun kendisi zaten kesin bir adres.
"""
from __future__ import annotations

import logging

import config

log = logging.getLogger(__name__)

SISTEM = """Sen bir Türk hukuku uzmanısın. Sana bir soru verilir, sen o
sorunun cevabını içerecek kanun maddesi hükmünü yazarsın.

Kurallar:
1. Gerçek madde numarası ya da kanun adı UYDURMA; yalnızca hüküm metnini yaz.
2. Kanun dilini kullan: "...zorundadır", "...feshedilemez", "...hakkı vardır".
3. TEK CÜMLE, en fazla 25 kelime.
4. Açıklama yapma, giriş cümlesi kurma.
5. Soru hukuki değilse yalnızca YOK yaz. Her soruyu zorla kanun diline
   çevirmeye çalışma."""

ISTEM = "Soru: {soru}\n\nBu sorunun cevabını içerecek kanun maddesi hükmünü yaz."

# Uretilen metin bu uzunlugu asarsa kirpiliyor: olculdu, uzun metin
# BM25'i yavaslatiyor ve isabeti dusuruyor.
EN_FAZLA_KARAKTER = 300


def varsayimsal_hukum(soru: str, uretici) -> str:
    """Soruyu cevaplayan varsayimsal hukum metni; uretilemezse bos doner."""
    try:
        c = uretici._gemini(ISTEM.format(soru=soru), sistem=SISTEM,
                            model=config.GEMINI_HIZLI_MODEL)
    except Exception as exc:
        log.warning("HyDE uretilemedi: %s", str(exc)[:80])
        return ""
    metin = (c or "").strip()
    # Hukuki olmayan soruda model "YOK" der. Bu cikis yolu ONEMLI: istem
    # ona "hukum yaz" diye emrettigi icin cikis yolu olmadan her soruyu
    # zorla kanun diline ceviriyordu -- "kahve nasil demlenir" sorusuna
    # "Isci, kahveyi kaynar su ile en az bes dakika demlemek suretiyle
    # hazirlamakla yukumludur" diye bir hukum uyduruyordu. Metin
    # kullaniciya gosterilmiyor ve guven puani ham sorudan olculuyor, yani
    # zararsizdi; yine de bosuna bir arama ve bir Gemini cagrisi.
    if metin.upper().startswith("YOK") or len(metin) < 20:
        return ""
    return metin[:EN_FAZLA_KARAKTER]
