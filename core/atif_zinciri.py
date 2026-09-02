"""Madde -> o maddeyi yorumlayan mahkeme kararlari dizini.

NE ISE YARIYOR
Bir maddeye bakarken "bu maddeyi Yargitay nasil yorumlamis" sorusunun
cevabini gosterir. Ticari veri tabanlari bu baglantiyi EDITORYAL kuruyor --
insanlar tek tek isaretliyor. Burada kararlarin kendi metninden otomatik
cikariliyor.

OLCULDU (400 karar ornegi):
    atif iceren karar     %76
    karar basina atif     3.8
    en cok atif yapilan   1475 m.14 (50x), 4857 m.17 (42x), 4857 m.21 (39x)

Yani kararlar dayandiklari maddeyi metinde acikca yaziyor ve bu metin
ayristirilabiliyor.

SINIRI
Atif cikarma metne dayaniyor; karar maddeyi ima edip numara vermediyse
baglanti kurulamaz. Yani dizin eksiksiz degil, "en az bunlar" listesidir.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import config
from core.atif import atiflari_cikar

log = logging.getLogger(__name__)

ZINCIR_YOLU = config.ROOT / "data" / "index_karar" / "atif_zinciri.json"

# Kanun adi -> numara. Kararlar bazen numara ("4857 sayili"), bazen ad
# ("Is Kanunu") kullaniyor; dizinin tek anahtarda toplanmasi icin
# adlar numaraya cevriliyor.
AD_NUMARA = {
    "iş kanunu": "4857",
    "is kanunu": "4857",
    "türk borçlar kanunu": "6098",
    "borçlar kanunu": "6098",
    "türk medeni kanunu": "4721",
    "medeni kanun": "4721",
    "türk ceza kanunu": "5237",
    "hukuk muhakemeleri kanunu": "6100",
    "sendikalar ve toplu iş sözleşmesi kanunu": "6356",
    "sosyal sigortalar ve genel sağlık sigortası kanunu": "5510",
    "iş mahkemeleri kanunu": "7036",
    "deniz iş kanunu": "854",
    "basın iş kanunu": "5953",
}


def _anahtar(kaynak: str, madde_no: str) -> str | None:
    """(kanun, madde) ciftini tek bir dizin anahtarina cevirir."""
    k = kaynak.strip().lower()
    if kaynak.isdigit():
        no = kaynak
    else:
        no = AD_NUMARA.get(k)
        if no is None:
            # "4857 sayili Is Kanunu" gibi karisik yazimlar
            for ad, numara in AD_NUMARA.items():
                if ad in k:
                    no = numara
                    break
        if no is None:
            return None
    return f"{no}-{madde_no}"


def _ozet(metin: str, en_fazla: int = 260) -> str:
    """Kararin kunye disi ilk cumlelerini doner.

    Uretilmis ozet degil, KARARIN KENDI metni. Boylece kullanici kararin
    ne hakkinda oldugunu tiklamadan gorur ve uydurma riski olmaz.
    """
    from scraper.karar_parser import kunye_at

    govde = kunye_at(metin)
    if not govde:
        return ""
    duz = " ".join(govde.split())
    if len(duz) <= en_fazla:
        return duz
    # Cumle ortasinda kesmemek icin son noktadan kirp
    kirpik = duz[:en_fazla]
    nokta = kirpik.rfind(". ")
    return (kirpik[:nokta + 1] if nokta > 120 else kirpik.rstrip()) + " …"


def atif_cumlesi(metin: str, madde_no: str, en_fazla: int = 300) -> str:
    """Kararda o maddeye atif yapilan cumleyi doner.

    Zincirde ILISKI var ama BAGLAM yoktu: kullanici "bu karar bu maddeye
    atif yapmis" bilgisini goruyor, ama maddenin kararda NASIL kullanildigini
    gormek icin karari acip aramak zorunda kaliyordu.

    Uretilmis metin degil, karardan birebir alinti.
    """
    if not metin or not madde_no:
        return ""
    kalip = re.compile(
        rf"[^.!?]*?\b{re.escape(madde_no)}\s*"
        rf"(?:\.|inci|nci|uncu|\u00fcnc\u00fc|\u0131nc\u0131)?\s*madde[^.!?]*[.!?]",
        re.IGNORECASE)
    m = kalip.search(metin)
    if not m:
        kalip2 = re.compile(rf"[^.!?]*?m\.\s*{re.escape(madde_no)}\b[^.!?]*[.!?]",
                            re.IGNORECASE)
        m = kalip2.search(metin)
    if not m:
        return ""
    cumle = " ".join(m.group(0).split()).strip()
    if len(cumle) < 30:
        return ""
    return cumle[:en_fazla] + (" …" if len(cumle) > en_fazla else "")


def kur(kararlar: list[dict], en_fazla_karar: int = 8,
        gecerli_maddeler: set[str] | None = None) -> dict[str, list[dict]]:
    """Kararlardan madde -> karar dizini kurar.

    en_fazla_karar: bir madde icin saklanacak karar sayisi. Kidem tazminati
    gibi maddelere yuzlerce karar atif yapiyor; hepsini saklamak dizini
    sisiriyor ve kullaniciya da yaramıyor.

    gecerli_maddeler: kulliyatta gercekten var olan "{no}-{madde}" kumesi.
    Verilirse yalnizca bunlar indekslenir. Sart degil ama onemli -- metinden
    cikarim bazen olmayan maddeler uretiyor ("4857 m.438" gibi; Is
    Kanunu'nda 438. madde yok) ve bunlar kullaniciya olu baglanti olarak
    gorunur.
    """
    from scraper.karar_parser import html_metne

    dizin: dict[str, list[dict]] = defaultdict(list)
    for k in kararlar:
        metin = html_metne(k.get("metin", ""))
        if not metin:
            continue
        kimlik = {
            "karar_id": str(k.get("id", "")),
            "daire": (k.get("daire") or "").strip(),
            "esas_no": k.get("esas_no", ""),
            "karar_no": k.get("karar_no", ""),
            "tarih": k.get("karar_tarihi", ""),
            # Kararin KENDI ilk cumleleri. Ozet uretilmiyor -- uretilen ozet
            # uydurma riski tasir; burada karardan alinti var.
            "ozet": _ozet(metin),
        }
        gorulen: set[str] = set()
        for kaynak, madde_no in atiflari_cikar(metin, en_fazla=20):
            a = _anahtar(kaynak, madde_no)
            if a is None or a in gorulen:
                continue
            if gecerli_maddeler is not None and a not in gecerli_maddeler:
                continue                # kulliyatta olmayan madde
            gorulen.add(a)
            if len(dizin[a]) < en_fazla_karar:
                # Atif cumlesi maddeye ozel: ayni karar farkli maddelere
                # farkli cumlelerde atif yapiyor.
                dizin[a].append({**kimlik,
                                 "atif_cumlesi": atif_cumlesi(metin, madde_no)})

    return dict(dizin)


def gecerli_madde_kumesi(kayitlar: list[dict]) -> set[str]:
    """Kulliyattaki "{mevzuat_no}-{madde_no}" kumesini doner."""
    return {f"{k.get('mevzuat_no')}-{k.get('madde_no')}" for k in kayitlar}


def kaydet(dizin: dict, yol: Path | None = None) -> None:
    yol = yol or ZINCIR_YOLU
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(dizin, ensure_ascii=False), encoding="utf-8")
    log.info("atif zinciri yazildi: %d madde", len(dizin))


class AtifZinciri:
    """Kurulmus dizini okuyup madde -> kararlar sorgusu yapar."""

    def __init__(self, yol: Path | None = None):
        self.yol = yol or ZINCIR_YOLU
        self._dizin: dict | None = None

    def _yukle(self) -> dict:
        if self._dizin is None:
            if self.yol.exists():
                self._dizin = json.loads(self.yol.read_text(encoding="utf-8"))
            else:
                self._dizin = {}
        return self._dizin

    def hazir_mi(self) -> bool:
        return bool(self._yukle())

    def kararlar(self, mevzuat_no: str, madde_no: str) -> list[dict]:
        return self._yukle().get(f"{mevzuat_no}-{madde_no}", [])

    def sayi(self) -> int:
        return len(self._yukle())
