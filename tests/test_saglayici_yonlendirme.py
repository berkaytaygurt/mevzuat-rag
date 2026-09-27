"""PROVIDER=local dendiginde hicbir sey Gemini'ye gitmemeli.

NEDEN AYRI BIR TEST DOSYASI

Bu bir gizlilik ozelligi, davranis ayrintisi degil. Avukat
PROVIDER=local dediginde dilekcesinin bilgisayardan cikmadigini
varsayiyor; varsayim yanlissa ogrendigi an guven biter.

Bir sure bu varsayim GERCEKTEN YANLISTI: hyde.py, mesele.py,
karsi_taraf.py ve canli_karar.py dogrudan uretici._gemini() cagiriyordu
ve PROVIDER ayarina hic bakmiyordu. Tek koruma GEMINI_API_KEY'in
tanimli olmamasiydi -- anahtari olan kullanicinin belgesi sessizce
disari cikiyordu.

Asagidaki iki testten ikincisi kaynak koda bakiyor. Bu alisilmadik ama
kasitli: ilk test yalnizca BUGUN var olan cagrilari korur, ikincisi
YARIN eklenecek olani da yakalar.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.generate import Generator

KOK = Path(__file__).resolve().parent.parent


def test_yerel_saglayicida_gemini_cagrilmiyor(monkeypatch):
    u = Generator(provider="local")

    def patla(*a, **k):
        raise AssertionError("PROVIDER=local iken Gemini cagrildi")

    monkeypatch.setattr(u, "_gemini", patla)
    monkeypatch.setattr(u, "_local", lambda *a, **k: "yerel cevap")

    assert u.kisa("soru") == "yerel cevap"


def test_gemini_saglayicisinda_gemini_cagriliyor(monkeypatch):
    """Ters yon de korunmali, yoksa test yalnizca 'hic cagirma' derdi."""
    u = Generator(provider="gemini")
    monkeypatch.setattr(u, "_gemini", lambda *a, **k: "bulut cevap")
    monkeypatch.setattr(u, "_local", lambda *a, **k: "yerel cevap")

    assert u.kisa("soru") == "bulut cevap"


# core/ icinde _gemini()'yi dogrudan cagirmasina izin verilen tek yer
# Generator'in kendisi (kisa() ve cevapla() oradan yonlendiriyor).
MUAF = {"generate.py"}
CAGRI = re.compile(r"\w+\._gemini\s*\(")


@pytest.mark.parametrize(
    "yol", sorted(p for p in (KOK / "core").glob("*.py") if p.name not in MUAF),
    ids=lambda p: p.name)
def test_modul_dogrudan_gemini_cagirmiyor(yol: Path):
    """Yeni bir yardimci cagri eklendiginde bu test uyarir.

    Dogru kullanim: uretici.kisa(...) -- saglayiciya gore yonlenir.
    Yanlis kullanim: uretici._gemini(...) -- PROVIDER ne olursa olsun
    buluta gider.
    """
    metin = yol.read_text(encoding="utf-8")
    bulunan = [s for i, s in enumerate(metin.splitlines(), 1)
               if CAGRI.search(s) and not s.lstrip().startswith("#")]
    assert not bulunan, (
        f"{yol.name} dogrudan _gemini() cagiriyor; kisa() kullanin:\n"
        + "\n".join("    " + s.strip() for s in bulunan))
