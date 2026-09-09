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


def _kod_satirlari() -> list[tuple[int, str]]:
    """Yorum satirlari haric, numarali kod satirlari.

    Bu dosyadaki denge sayimlari kaba: tirnak ve parantezleri sayiyor.
    Turkce yorumlarda kesme isareti ("PDF'ten") ve dengesiz parantez
    ('bent duzeyinde ("a)")') dogal olarak geciyor ve sahte alarm
    uretiyordu. Denetlenmesi gereken KOD; duzyazi degil.

    BLOK YORUMLAR da atlaniyor. Once yalnizca "//" satirlari
    atlaniyordu; bir /* ... */ blogunda gecen bir kesme isareti
    ("localStorage'inda") sahte alarm uretti. Ayni gerekce, ayni
    cozum -- duzyazi denetim disi.
    """
    satirlar = []
    blokta = False
    for i, s in enumerate(_script().split(chr(10)), 1):
        kirpik = s.strip()
        if blokta:
            if "*/" in kirpik:
                blokta = False
                kalan = kirpik.split("*/", 1)[1]      # kapanistan sonrasi kod
                if kalan.strip():
                    satirlar.append((i, kalan))
            continue
        if kirpik.startswith("//"):
            continue
        if kirpik.startswith("/*"):
            if "*/" not in kirpik:
                blokta = True
            continue
        satirlar.append((i, s))
    return satirlar


def test_tek_tirnakli_dizgide_kacissiz_tirnak_yok():
    """Tek tirnakli JS dizgisi icinde kacissiz ' varsa script cokuyor."""
    bozuk = []
    for i, satir in _kod_satirlari():
        # Kacisli tirnaklari cikarip say: tek sayi kaliyorsa dizgi kapanmamis
        temiz = satir.replace("\\'", "")
        if temiz.count("'") % 2 == 1:
            bozuk.append((i, satir.strip()[:80]))
    assert not bozuk, f"kapanmamis tek tirnak: {bozuk}"


def test_parantez_dengesi():
    kod = "\n".join(s for _, s in _kod_satirlari())
    assert kod.count("{") == kod.count("}"), "suslu parantez dengesiz"
    assert kod.count("(") == kod.count(")"), "parantez dengesiz"


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
    assert "function ciz(d, sessiz)" in js
    assert 'querySelectorAll(".sekme")' in js


def test_konusma_akisi_ustune_yaziyor_degil_ekliyor():
    """Ikinci soru birincinin cevabini silmemeli.

    Once ciz() her cagrisinda ciktiEl.innerHTML'i bastan yaziyordu; ikinci
    soru sorulunca birinci cevap ekrandan siliniyor ve geri donusu
    kalmiyordu. Simdi her soru-cevap bir .konusma blogu olarak ekleniyor.
    """
    js = _script()
    assert "ciktiEl.appendChild(blok)" in js
    # Cevap cizen yolda innerHTML ile bastan yazma kalmamali; yalnizca
    # akisi temizleyen yerlerde (yeni sohbet, sohbet degistirme) var.
    assert 'ciktiEl.innerHTML = h' not in js
    assert "function konusmayiCiz(dosya)" in js


def test_sekme_kendi_konusmasinda_calisir():
    """Sekmeye basmak butun konusmalarin panellerini degistirmemeli."""
    js = _script()
    assert "function sekmeSec(blok, no)" in js
    assert 'blok.querySelectorAll(".panel")' in js


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


def test_karar_kartlari_acilabiliyor():
    """Karar kartlari .karar sinifini tasiyor; acma kurali onu da kapsamali.

    Kural yalnizca .madde icin yaziliydi: karara tiklaninca "acik" sinifi
    ekleniyor ama hicbir CSS kurali eslesmedigi icin govde gizli kaliyordu.
    Kararlar HIC acilmiyordu.
    """
    h = ARAYUZ.read_text(encoding="utf-8")
    assert ".karar.acik .madde-govde" in h, "karar kartlari acilmiyor"
    assert ".karar.acik .ok" in h


def test_madde_metni_fikralara_bolunuyor():
    js = _script()
    assert "function fikralara" in js
    # Ucu de fikra bolmeyi kullanmali: dayanak, karsi taraf, kararlar
    assert js.count("fikralara(") >= 4, "fikra bolme her yerde kullanilmamis"


def test_basliksiz_maddede_metin_onizlemesi():
    """Baslik yoksa "(basliksiz madde)" degil, metnin basi gosterilmeli.

    Olculdu: maddelerin %7,4'u (20.253) gercekten baslik tasimiyor --
    degisiklik kanunlari, yururluk/yurutme maddeleri, gecici maddeler.
    PDF'te de baslik satiri yok, yani ayristirici hatasi degil. Ama
    "(basliksiz madde)" etiketi avukata hicbir sey soylemiyor.
    """
    js = _script()
    assert "function maddeEtiketi" in js
    assert "(başlıksız madde)" not in js, "eski yer tutucu duruyor"
    assert "madde-onizleme" in js
