"""Belge yukleme ucunun uctan uca davranisi.

Kimlik dogrulama bagimliligi test icin devre disi birakiliyor; amac
sifreyi kullanmak degil, ucun davranisini olcmek.

Bu testler ANALIZ adimini calistirmiyor: o adim Gemini cagiriyor ve
model + indeks yuklemesi gerektiriyor. Olculen sey ilk adim, yani
"belge yerelde okundu, maskelendi, disari hicbir sey gitmeden onaya
sunuldu" kismi -- gizlilik acisindan kritik olan da bu.
"""
from __future__ import annotations

import io

import pytest

pymupdf = pytest.importorskip("pymupdf")

from fastapi.testclient import TestClient   # noqa: E402

import server                                # noqa: E402


@pytest.fixture()
def istemci():
    server.app.dependency_overrides[server.kimlik] = lambda: "test"
    with TestClient(server.app) as c:
        yield c
    server.app.dependency_overrides.clear()


def _pdf_uret(metin: str) -> bytes:
    belge = pymupdf.open()
    sayfa = belge.new_page()
    yazitipi = pymupdf.Font(fontfile=r"C:\Windows\Fonts\arial.ttf")
    yazici = pymupdf.TextWriter(sayfa.rect)
    y = 60.0
    for satir in metin.split("\n"):
        if satir.strip():
            yazici.append((50, y), satir, font=yazitipi, fontsize=10)
        y += 14
    yazici.write_text(sayfa)
    veri = belge.tobytes()
    belge.close()
    return veri


DILEKCE = """ANKARA 5. IS MAHKEMESI SAYIN HAKIMLIGINE
DAVACI : Ahmet Yılmaz (T.C. 10000000146)
ADRES : Kızılay Mah. Atatürk Bulvarı No:5/12 Çankaya/ANKARA
TELEFON : 0532 111 22 33
DAVALI : Örnek Yapı Sanayi ve Ticaret A.Ş.
Müvekkilin savunması alınmadan iş akdi feshedilmiştir.
4857 sayılı İş Kanunu m.19 uyarınca savunma alınması zorunludur.
Yargıtay 9. Hukuk Dairesi 2019/1234 E. 2021/567 K. sayılı kararı."""


def test_pdf_yuklenince_maskeli_metin_donuyor(istemci):
    r = istemci.post("/api/belge", files={
        "dosya": ("dilekce.pdf", _pdf_uret(DILEKCE), "application/pdf")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["oturum"] and d["maskeli"]
    assert d["ozet"].get("TCKN") == 1
    assert d["ozet"].get("TEL") == 1


def test_tanimlayicilar_cevapta_yok(istemci):
    """EN ONEMLI TEST: uc, gizlenen degerleri geri gondermemeli.

    Maskeli metin tarayiciya gidiyor; esleme tablosu sunucunun
    (kullanicinin kendi makinesinin) belleginde kaliyor.
    """
    r = istemci.post("/api/belge", files={
        "dosya": ("dilekce.pdf", _pdf_uret(DILEKCE), "application/pdf")})
    govde = r.text
    for gizli in ("Ahmet Yılmaz", "10000000146", "0532 111 22 33",
                  "Kızılay", "Örnek Yapı"):
        assert gizli not in govde, f"tanimlayici cevaba sizdi: {gizli}"


def test_hukuk_atiflari_maskeli_metinde_duruyor(istemci):
    """Bunlar bozulursa analiz coker ve sebebi gorunmez."""
    r = istemci.post("/api/belge", files={
        "dosya": ("dilekce.pdf", _pdf_uret(DILEKCE), "application/pdf")})
    maskeli = r.json()["maskeli"]
    for iz in ("4857", "m.19", "9. Hukuk Dairesi", "2019/1234", "2021/567"):
        assert iz in maskeli, f"atif kayboldu: {iz}"


def test_desteklenmeyen_bicim_reddediliyor(istemci):
    r = istemci.post("/api/belge", files={
        "dosya": ("belge.docx", b"PK\x03\x04sahte", "application/octet-stream")})
    assert r.status_code == 400


def test_bos_pdf_anlasilir_hata_veriyor(istemci):
    """Taranmis PDF'te metin katmani yoktur; kullanici sebebini bilmeli."""
    belge = pymupdf.open()
    belge.new_page()
    veri = belge.tobytes()
    belge.close()
    r = istemci.post("/api/belge", files={
        "dosya": ("bos.pdf", veri, "application/pdf")})
    assert r.status_code == 422
    assert "metin" in r.json()["detail"].lower()


def test_bilinmeyen_oturum_reddediliyor(istemci):
    r = istemci.post("/api/belge/analiz", json={
        "oturum": "olmayan", "maskeli": "deneme"})
    assert r.status_code == 404


def test_txt_de_okunuyor(istemci):
    r = istemci.post("/api/belge", files={
        "dosya": ("olay.txt", DILEKCE.encode("utf-8"), "text/plain")})
    assert r.status_code == 200
    assert "[TCKN_1]" in r.json()["maskeli"]
