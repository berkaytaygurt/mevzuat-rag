"""Parser regresyon testleri.

Buradaki her test, gelistirme sirasinda gercekten karsilasilan bir hataya
karsilik gelir. Ag baglantisi gerektirmez; onbellekteki PDF'leri kullanir,
yoksa testi atlar.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.parser import (  # noqa: E402
    MADDE_RE, BOLUM_RE, _baslik_olabilir, maddeleri_cikar, parse_pdf,
)

PDF_DIZIN = ROOT / "data" / "raw"


def _pdf(no: str) -> bytes:
    yol = PDF_DIZIN / f"_probe_{no}.pdf"
    if not yol.exists():
        pytest.skip(f"onbellekte {yol.name} yok")
    return yol.read_bytes()


# --------------------------------------------------------------------------
# Regex davranisi
# --------------------------------------------------------------------------
@pytest.mark.parametrize("satir,beklenen_no", [
    ("Madde 1 - Bu Kanunun amaci", "1"),
    ("MADDE 12 - Belirli sureli", "12"),
    ("Madde 5 – (Ek: 6/2/2014-6518/57 md.)", "5"),      # en-dash
    ("Ek Madde 3 - Zamanasimi", "3"),
    ("Geçici Madde 8- (Ek: 12/10/2017)", "8"),           # bosluksuz tire
])
def test_madde_regex_yakalar(satir, beklenen_no):
    m = MADDE_RE.match(satir)
    assert m is not None, f"eslesmedi: {satir}"
    assert m.group("no") == beklenen_no


@pytest.mark.parametrize("satir", [
    "Bu maddede gecen madde 5 ifadesi",   # cumle icinde
    "Yillik ucretli izin hakki",
])
def test_madde_regex_yanlis_pozitif_vermez(satir):
    assert MADDE_RE.match(satir) is None


def test_bolum_regex():
    assert BOLUM_RE.match("BİRİNCİ BÖLÜM")
    assert BOLUM_RE.match("İKİNCİ KISIM")
    assert not BOLUM_RE.match("Bu bölümde yer alan hükümler")


# --------------------------------------------------------------------------
# Baslik secimi -- Is Kanunu'nda liste ogesi baslik sanilmisti
# --------------------------------------------------------------------------
def test_liste_ogesi_baslik_sayilmaz():
    assert not _baslik_olabilir("d) İş sözleşmesinin eşit davranma ilkesine")
    assert not _baslik_olabilir("(2) Fiil daha ağır cezayı gerektiren")


def test_numarali_baslik_kabul_edilir():
    """TMK 'II. Malvarligi', '1. Genel olarak' gibi basliklar kullanir."""
    assert _baslik_olabilir("II. Malvarlığının tasfiyesi")
    assert _baslik_olabilir("1. Genel olarak")


def test_uzun_satir_baslik_sayilmaz():
    assert not _baslik_olabilir("x" * 120)


# --------------------------------------------------------------------------
# Uctan uca: gercek kanun PDF'leri
# --------------------------------------------------------------------------
@pytest.mark.parametrize("no,son_madde", [
    ("4857", 122),    # Is Kanunu
    ("4721", 1030),   # Turk Medeni Kanunu -- iframe bunu 425'te kesiyordu
    ("6098", 649),    # Turk Borclar Kanunu -- iframe 486'da kesiyordu
])
def test_kanun_tam_ayristirilir(no, son_madde):
    maddeler = parse_pdf(_pdf(no), tur_adi="Kanun", mevzuat_no=no, tertip="5")
    numaralar = [int(m.madde_no) for m in maddeler if m.madde_no.isdigit()]
    assert max(numaralar) == son_madde, "kanun eksik ayristirildi"
    assert min(numaralar) == 1


def test_chunk_id_benzersiz():
    """Ayni chunk_id vektor deposunda kaydin ustune yazar."""
    maddeler = parse_pdf(_pdf("4857"), tur_adi="Kanun", mevzuat_no="4857", tertip="5")
    idler = [m.chunk_id for m in maddeler]
    assert len(idler) == len(set(idler))


def test_mojibake_yok():
    """PDF yolunda cift-encode bozulmasi olmamali (HTML yolunda vardi)."""
    maddeler = parse_pdf(_pdf("4721"), tur_adi="Kanun", mevzuat_no="4721", tertip="5")
    tum = " ".join(m.metin for m in maddeler)
    for imza in ("Ã¶", "Ä±", "Å", "Ã§"):
        assert imza not in tum, f"mojibake izi: {imza}"


def test_degisiklik_listesi_madde_sayilmaz():
    """Belge sonundaki 'EK VE DEGISIKLIK GETIREN...' listesi metne sizmamali."""
    maddeler = parse_pdf(_pdf("4857"), tur_adi="Kanun", mevzuat_no="4857", tertip="5")
    son = maddeler[-1]
    assert "DEĞİŞİKLİK GETİREN" not in son.metin


def test_mulga_tespit_edilir():
    maddeler = parse_pdf(_pdf("4857"), tur_adi="Kanun", mevzuat_no="4857", tertip="5")
    assert any(m.mulga for m in maddeler), "hicbir mulga madde bulunamadi"


def test_baslik_kapsami_yuksek():
    maddeler = parse_pdf(_pdf("4721"), tur_adi="Kanun", mevzuat_no="4721", tertip="5")
    baslikli = sum(1 for m in maddeler if m.baslik)
    assert baslikli / len(maddeler) > 0.95


def test_embed_metni_baglami_icerir():
    maddeler = parse_pdf(_pdf("4857"), tur_adi="Kanun", mevzuat_no="4857", tertip="5")
    m53 = next(m for m in maddeler if m.madde_no == "53")
    metin = m53.to_embed_text()
    assert "İŞ KANUNU" in metin
    assert "Madde 53" in metin
    assert "Yıllık ücretli izin" in metin


def test_bos_girdi_cokmez():
    assert maddeleri_cikar([]) == []
    assert maddeleri_cikar(["rastgele metin", "madde yok"]) == []


# --------------------------------------------------------------------------
# Baslik kalitesi -- kulliyatin %19.5'inde baslik cumle parcasiydi
# --------------------------------------------------------------------------
@pytest.mark.parametrize("satir", [
    "eklenmiştir.",
    "yürürlüğe girer.",
    "devam olunur.",
    "memur ve ilgililer çağrılabilir.",
    "Türkiye’de hemşirelik mesleğini icra edemez.",
])
def test_cumle_parcasi_baslik_sayilmaz(satir):
    """Onceki maddenin son cumlesi baslik sanilıyordu. Yanlis baslik BM25
    metninde uc kez tekrarlandigi icin indeksi zehirliyor."""
    assert not _baslik_olabilir(satir)


@pytest.mark.parametrize("satir", [
    "Amaç ve kapsam",
    "Yıllık ücretli izin hakkı ve izin süreleri",
    "II. Malvarlığının tasfiyesi",
    "1. Genel olarak",
    "Genel baraj ve hesaplanması:",
])
def test_gercek_baslik_kabul_edilir(satir):
    assert _baslik_olabilir(satir)


def test_kunye_satiri_baslik_sayilmaz():
    assert not _baslik_olabilir(": Tertip: 3 Cilt: 30 Sayfa: 1085")
