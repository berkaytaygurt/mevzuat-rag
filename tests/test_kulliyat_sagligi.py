"""Kulliyatin bilinen maddelerini denetler.

NEDEN VAR
02.09.2026'da iki gun ust uste ayni sinifta hata yasandi:

1. Dipnot, maddenin iki fikrasi arasina dusuyor ve ayristirici maddeyi
   orada kapatiyordu. Is Kanunu m.19 kulliyata 112 karakter olarak
   girmisti; "savunmasini almadan ... feshedilemez" fikrasi HIC YOKTU.
   Sistem ise iade sorularinda dayanak bulamiyordu ve sebebi gorunmuyordu.

2. Duzeltmenin ilk hali yalnizca PUNTOYA bakiyordu. Kanunlarda calisti
   ama yonetmeliklerde govdenin bir kismi zaten kucuk puntoyla dizili
   oldugu icin GERCEK MADDE METNI siliniyordu: 8342 sayili yonetmelikte
   3.211 satirin 1.204'u, "Madde 1 - Bu Yonetmelik, av ve yaban
   hayvanlarinin..." dahil.

Iki hata da testlerden gecti, cunku testler AYRISTIRICIYI sinifiyordu,
KULLIYATI degil. Bu dosya kulliyatin kendisine bakiyor: birkac bilinen
maddenin gercekten yerinde ve tam oldugunu dogruluyor.

Kulliyat yoksa testler atlanir; depoda veri tutulmuyor.
"""
import json
from functools import lru_cache

import pytest

import config

KULLIYAT = config.RAW_DIR / "maddeler.json"

# (mevzuat_no, madde_no, metinde MUTLAKA gecmesi gereken ifade, en az uzunluk)
BILINEN_MADDELER = [
    # Dipnot yuzunden kaybolan fikra; bu testin var olma sebebi
    ("4857", "19", "savunmasını almadan", 300),
    ("4857", "53", "yıllık ücretli izin", 300),
    ("4857", "18", "geçerli bir sebebe dayanmak", 200),
    ("6098", "344", "kira bedeli", 300),
    ("4721", "166", "temelinden sarsılmış", 200),
    ("5237", "125", "onur, şeref ve saygınlığını", 200),
    ("6698", "5", "açık rızası", 300),
]

# Punto suzgecinin gercek metni sildigi yonetmelikler
BILINEN_YONETMELIKLER = [
    ("8342", "1", "av ve yaban hayvanlarının", 150),
]


@lru_cache(maxsize=1)
def _kulliyat():
    if not KULLIYAT.exists():
        return None
    return json.loads(KULLIYAT.read_text(encoding="utf-8"))


def _madde(kayitlar, no, madde_no):
    for k in kayitlar:
        if k.get("mevzuat_no") == no and str(k.get("madde_no")) == madde_no:
            return k
    return None


@pytest.fixture(scope="module")
def kulliyat():
    k = _kulliyat()
    if k is None:
        pytest.skip("kulliyat yok (data/raw/maddeler.json)")
    return k


@pytest.mark.parametrize("no,madde_no,ifade,en_az",
                         BILINEN_MADDELER + BILINEN_YONETMELIKLER)
def test_bilinen_madde_tam(kulliyat, no, madde_no, ifade, en_az):
    m = _madde(kulliyat, no, madde_no)
    assert m is not None, f"{no} m.{madde_no} kulliyatta yok"
    metin = m["metin"]
    assert len(metin) >= en_az, (
        f"{no} m.{madde_no} kisalmis: {len(metin)} karakter (en az {en_az})")
    assert ifade.lower() in metin.lower(), (
        f"{no} m.{madde_no} icinde '{ifade}' yok -- madde kesilmis olabilir")


def test_harfli_madde_govdede_kalmadi(kulliyat):
    """'Madde 3/A' harfi numaraya girmeli, govdenin basinda kalmamali."""
    import re
    kalan = [k for k in kulliyat
             if re.match(r"^/[A-ZÇĞİÖŞÜ]", k.get("metin", ""))]
    assert not kalan, f"{len(kalan)} maddenin govdesi '/HARF' ile basliyor"


def test_dipnot_govdeye_sizmamis(kulliyat):
    """Dipnot metni madde govdesine karismamali.

    Ornek kirlilik: "... Bakanlar Kurulu yurutur 5 Bu maddede gecen
    '...belediyeler...' sozcugu; Anayasa Mahkemesinin ... iptal edilmistir."

    Esik MUTLAK sayida: oransal esik ise yaramadi. Olculdu -- duzeltme
    oncesi kulliyatta 187 madde, sonrasinda 16. Ikisi de 275 bin madde
    icinde binde bir bile degil, yani oransal bir esik iki durumu ayirt
    edemiyordu.
    """
    import re
    kalip = re.compile(r"\s\d{1,2}\s+Bu (maddede|bendin|fıkrada) ")
    kirli = [k for k in kulliyat if kalip.search(k.get("metin", ""))]
    assert len(kirli) < 60, f"{len(kirli)} maddede dipnot izi var (duzeltme sonrasi 16 idi)"


def test_kanun_hacmi_beklenen_bantta(kulliyat):
    """Kanun metinlerinin toplam hacmi.

    Dipnot duzeltmesinden sonra olculdu: 26,3 milyon karakter. Ciddi bir
    dususe (yeniden bir kesme hatasi) ya da ciddi bir artisa (gurultu
    sizmasi) karsi genis bir bant.
    """
    toplam = sum(len(k["metin"]) for k in kulliyat
                 if k.get("mevzuat_tur") == "Kanun")
    assert 23_000_000 < toplam < 30_000_000, (
        f"kanun metni hacmi beklenen bandin disinda: {toplam:,}")
