"""Arayuz JavaScript'inin bozuk olmadigini denetler.

NEDEN VAR
aibars.html icindeki script bir tirnak kacisi yuzunden UC KEZ tumuyle
coktu. Belirti sinsi: sunucu calisiyor, sayfa aciliyor, ama hicbir sey
tepki vermiyor ve durum gostergesi sonsuza kadar "hazirlaniyor" diyor --
cunku tum script tek bir SyntaxError ile devre disi kaliyor.

Hata her seferinde ayni yerden geldi: tek tirnakli bir JS dizgisi icinde
onclick="...toggle('acik')" yazarken ic tirnaklarin kacisi kayboldu.
"""
from pathlib import Path
import re

ARAYUZ = Path(__file__).resolve().parent.parent / "web" / "aibars.html"


def _script() -> str:
    h = ARAYUZ.read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", h, re.S)
    assert m, "aibars.html icinde <script> bulunamadi"
    return m.group(1)


def test_tek_tirnakli_dizgide_kacissiz_tirnak_yok():
    """Tek tirnakli JS dizgisi icinde kacissiz ' varsa script cokuyor."""
    bozuk = []
    for i, satir in enumerate(_script().split("\n"), 1):
        # Kacisli tirnaklari cikarip say: tek sayi kaliyorsa dizgi kapanmamis
        temiz = satir.replace("\\'", "")
        if temiz.count("'") % 2 == 1:
            bozuk.append((i, satir.strip()[:80]))
    assert not bozuk, f"kapanmamis tek tirnak: {bozuk}"


def test_parantez_dengesi():
    js = _script()
    assert js.count("{") == js.count("}"), "suslu parantez dengesiz"
    assert js.count("(") == js.count(")"), "parantez dengesiz"


def test_toggle_cagrilari_kacisli():
    """onclick icindeki toggle('acik') mutlaka kacisli olmali."""
    js = _script()
    kacissiz = re.findall(r"onclick=\"[^\"]*toggle\('", js)
    assert not kacissiz, f"kacissiz toggle: {kacissiz}"


def test_gerekli_fonksiyonlar_duruyor():
    js = _script()
    for ad in ("ciz", "sor", "durumGuncelle", "maddeMetni",
               "yorumlayanlar", "dogrulamaKutusu"):
        assert f"function {ad}" in js or f"{ad} =" in js, f"{ad} kayip"


def test_sekme_ve_panel_fonksiyonlari_var():
    """Sonuc sayfasi sekmeli: cevap ustte sabit, referans bolumleri sekmede."""
    js = _script()
    for ad in ("sekmeSec", "dayanakPaneli", "karsiPaneli", "kararPaneli",
               "yukleniyorGoster"):
        assert f"function {ad}" in js, f"{ad} kayip"


def test_panel_gorunurlugu_hidden_ile_yonetiliyor():
    js = _script()
    assert "p.hidden = p.dataset.panel !== no" in js


def test_ciz_hala_tek_giris_noktasi():
    """ciz() paneli kurup olay dinleyicilerini bagliyor."""
    js = _script()
    assert "function ciz(d)" in js
    assert 'querySelectorAll(".sekme")' in js


def test_sor_olay_dinleyicisine_dogrudan_baglanmiyor():
    """sor() ARGUMANSIZ cagrilmali.

    "gonderEl.onclick = sor" yazildiginda tiklama olayi birinci parametreye
    (secilen) dusuyor, netlestirme atlaniyor ve sorgu olarak MouseEvent
    gonderiliyordu; sunucu 422 donuyordu. Sitede boyle cikti.
    """
    js = _script()
    assert "onclick = sor;" not in js, "sor dogrudan olaya baglanmis"
    assert "addEventListener(\"click\", sor)" not in js
    assert "gonderEl.onclick = function () { sor(); };" in js


def test_sor_dizgi_olmayan_secileni_yok_sayiyor():
    js = _script()
    assert 'typeof secilen !== "string"' in js, "savunma kontrolu kayip"
