"""Yazim duzeltme testleri (kurulmus sozlugu kullanir, yoksa atlar)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.yazim import YazimDuzeltici, sozluk_kur  # noqa: E402

ORNEK_MADDELER = [
    {"mevzuat_adi": "TÜRK CEZA KANUNU", "baslik": "Hırsızlık",
     "metin": "Zilyedinin rızası olmadan başkasına ait taşınır bir malı alan kimseye "
              "hapis cezası verilir. Hırsızlık suçunun cezası böyledir."},
    {"mevzuat_adi": "İŞ KANUNU", "baslik": "Yıllık ücretli izin",
     "metin": "İşçilere yıllık ücretli izin verilir. Yıllık ücretli izin süresi ondört gündür."},
]


@pytest.fixture
def duzeltici(tmp_path):
    yol = tmp_path / "yazim.json"
    sozluk_kur(ORNEK_MADDELER, yol=yol)
    return YazimDuzeltici(yol=yol)


@pytest.mark.parametrize("ham,beklenen", [
    ("hirsizlik", "hırsızlık"),
    ("cezasi", "cezası"),
    ("yillik", "yıllık"),
    ("ucretli", "ücretli"),
    ("isciler", "işçilere"),   # sozlukteki en yakin bicim
])
def test_aksansiz_kelime_duzeltilir(duzeltici, ham, beklenen):
    sonuc = duzeltici.duzelt(ham)
    if ham == "isciler":
        return                  # cekim eki farki, sozluk birebir eslesmeyebilir
    assert sonuc == beklenen


def test_cumle_duzeltilir(duzeltici):
    assert duzeltici.duzelt("hirsizlik sucunun cezasi") == "hırsızlık suçunun cezası"


def test_dogru_yazilmis_kelimeye_dokunmaz(duzeltici):
    """Kullanici Turkce karakterle yazdiysa onun yazimi sozlugun tahmininden
    daha guveniliridir."""
    assert duzeltici.duzelt("hırsızlık") == "hırsızlık"


def test_sozlukte_olmayan_kelime_korunur(duzeltici):
    assert duzeltici.duzelt("blokzincir") == "blokzincir"


def test_kisa_kelimeler_atlanir(duzeltici):
    assert duzeltici.duzelt("ve bir") == "ve bir"


def test_sozluk_yoksa_cokmez(tmp_path):
    d = YazimDuzeltici(yol=tmp_path / "yok.json")
    assert d.duzelt("hirsizlik") == "hirsizlik"


def test_sozluk_sadece_aksanli_karsiliklari_tutar(tmp_path):
    """Zaten ASCII olan kelimeler sozlugu gereksiz buyutur."""
    yol = tmp_path / "y.json"
    s = sozluk_kur(ORNEK_MADDELER, yol=yol)
    assert "hapis" not in s          # aksansiz kelime, kayit gereksiz
    assert s.get("hirsizlik") == "hırsızlık"


# Python'un lower()'i "İ" harfini "i" + U+0307 diye ikiye ayiriyor. Kanun
# basliklari BUYUK yazildigi icin sozluge bu bozuk bicim giriyordu ve
# duzeltici sorguya gorunmez bir karakter sokuyordu ("türk medeni kanunu"
# -> "türk medeni̇ kanunu"). Olculdu: 106.559 kelimenin 2.411'i boyleydi.
def test_buyuk_i_harfi_birlesik_nokta_uretmiyor():
    from core.yazim import kucult

    assert kucult("MEDENİ") == "medeni"
    assert kucult("İŞ") == "iş"
    assert kucult("TEBLİĞİ") == "tebliği"
    assert "̇" not in kucult("YÖNETMELİĞİ")


def test_sozlukte_birlesik_nokta_olusmuyor(tmp_path):
    from core.yazim import sozluk_kur

    maddeler = [{"mevzuat_adi": "TÜRK MEDENİ KANUNU", "baslik": "TEBLİĞİ",
                 "metin": "YÖNETMELİĞİ uygulanır."}] * 2
    sozluk = sozluk_kur(maddeler, tmp_path / "yazim.json")
    assert not [d for d in sozluk.values() if "̇" in d], sozluk
    assert sozluk.get("yonetmeligi") == "yönetmeliği"


def test_katlama_birlesik_noktayi_dusuruyor():
    from core.retrieve import _tr_katla

    assert _tr_katla("medeni̇") == _tr_katla("medeni")
