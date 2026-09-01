"""Cevap metninden mevzuat atiflarini cikarir.

Neden ayri bir modul: atif bicimleri sanildigindan cok cesitli ve ilk iki
denemede desen yanlis yazildigi icin olcum bozuldu. Olculdu -- yalnizca
"m.14" ve "Madde 14" araniyordu; Gemini ise soyle yaziyor:

    "1475 sayili (Eski) Is Kanunu'nun halen yururlukte olan **14. maddesi**"

yani sayiyi "madde" kelimesinden ONCE koyuyor ve markdown yildizi kullaniyor.
Bu yuzden "Gemini hic kaynak gostermiyor" gibi yanlis bir sonuc cikmisti.

Desteklenen bicimler:
    m.53 / m. 53
    Madde 53 / madde 53
    53. maddesi / 53 uncu maddesi / 53 inci madde
    (IS KANUNU - Madde 53)
    4857 sayili Is Kanunu ... 41
"""
from __future__ import annotations

import re

# "4857 sayılı", "1475 sayili"
KANUN_NO_RE = re.compile(r"(\d{3,4})\s*say[ıi]l[ıi]", re.IGNORECASE)

# "İş Kanunu", "Türk Borçlar Kanunu", "İŞ KANUNU"
# IGNORECASE sart: mevzuat adi kimi yerde tamamen buyuk harfle yaziliyor
# ("İŞ KANUNU - Madde 53") ve kucuk/buyuk duyarli desen bunu kaciriyordu.
# {1,50}: "İŞ KANUNU" gibi kisa adlar da yakalanmali. {3,50} iken bu ad
# eslesmiyordu ve "(İŞ KANUNU - Madde 53)" bicimindeki atiflar kaciyordu.
KANUN_ADI_RE = re.compile(
    r"([A-ZÇĞİÖŞÜa-zçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü\s]{1,50}?Kanunu?)\b",
    re.IGNORECASE)
# Kanun adi eslesmesinin basina takilan doldurma kelimeler
_ONEK_TEMIZ = re.compile(r"^(?:say[ıi]l[ıi]|ve|ile|olan|eski|yeni)\s+",
                         re.IGNORECASE)

# Madde numarasi: uc ayri bicim
MADDE_RE = re.compile(
    r"m\.\s*(\d{1,3})\b"                                   # m.53
    r"|[Mm]adde\s*[:\-]?\s*(\d{1,3})\b"                    # Madde 53
    r"|(\d{1,3})\s*(?:\.|inci|nci|uncu|üncü|ıncı|ncı)?\s*madde",  # 53. maddesi
    re.IGNORECASE)


def temizle(metin: str) -> str:
    """Markdown isaretlerini ve fazla bosluklari atar."""
    m = re.sub(r"[*_`#]", " ", metin or "")
    return re.sub(r"\s+", " ", m)


def atiflari_cikar(cevap: str, en_fazla: int = 6) -> list[tuple[str, str]]:
    """(kaynak, madde_no) ciftlerini doner.

    kaynak, ya kanun numarasi ("4857") ya da kanun adidir ("İş Kanunu").
    Her madde numarasi, metinde kendisinden ONCE gelen en yakin kaynakla
    eslestirilir; solunda kaynak yoksa en yakin kaynak kullanilir.
    """
    metin = temizle(cevap)

    kaynaklar: list[tuple[int, str]] = []
    for m in KANUN_NO_RE.finditer(metin):
        kaynaklar.append((m.start(), m.group(1)))
    for m in KANUN_ADI_RE.finditer(metin):
        ad = _ONEK_TEMIZ.sub("", m.group(1).strip())
        if len(ad) >= 6:
            kaynaklar.append((m.start(), ad))
    if not kaynaklar:
        return []

    # Kanun numarasi ada tercih edilir: "4857" tek anlamli, "İş Kanunu" degil
    # (Deniz Is Kanunu, Basin Is Kanunu... hepsi eslesebiliyor).
    numaralar = {k for k, v in kaynaklar if v.isdigit()}

    sonuc: list[tuple[str, str]] = []
    for m in MADDE_RE.finditer(metin):
        no = next((g for g in m.groups() if g), None)
        if not no or int(no) == 0:
            continue
        sol = [(m.start() - k, v) for k, v in kaynaklar if k <= m.start()]
        # Yakinda bir kanun numarasi varsa onu kullan
        sayisal = [(u, v) for u, v in sol if v.isdigit() and u < 120]
        if sayisal:
            _, kaynak = min(sayisal)
        elif sol:
            _, kaynak = min(sol)
        else:
            _, kaynak = min((abs(k - m.start()), v) for k, v in kaynaklar)
        sonuc.append((kaynak, no))

    gorulen: set[tuple[str, str]] = set()
    temiz: list[tuple[str, str]] = []
    for c in sonuc:
        if c not in gorulen:
            gorulen.add(c)
            temiz.append(c)
    return temiz[:en_fazla]


def madde_bul(maddeler: list[dict], kaynak: str, madde_no: str) -> dict | None:
    """Atifta gosterilen maddeyi kulliyatta arar; bulamazsa None."""
    kaynak_k = kaynak.lower().strip()
    numara = kaynak.isdigit()
    for m in maddeler:
        if str(m.get("madde_no", "")).strip() != madde_no:
            continue
        if numara:
            if m.get("mevzuat_no") == kaynak:
                return m
            continue
        ad = (m.get("mevzuat_adi") or "").lower()
        if kaynak_k in ad or ad in kaynak_k:
            return m
    return None
