"""Danistay istemcisinin govde sekli ve metin temizligi.

NEDEN VAR
Danistay ucu Yargitay'dan FARKLI govde bekliyor: cogul ve dizi alanlar
(andKelimeler = ["\"mobbing\""]). Tekil "andKelime" gonderilince sunucu
"Lutfen arama kriterlerini giriniz!" diyor. Bu ayrim kolayca kaybolur;
teste baglandi.
"""
import re

from scraper.danistay import DanistayClient, _bos_govde, CaptchaAcik
from scraper.karar_parser import html_metne


def test_govde_cogul_dizi_alanlar_tasiyor():
    g = _bos_govde()
    for alan in ("andKelimeler", "orKelimeler", "notAndKelimeler", "notOrKelimeler"):
        assert alan in g and isinstance(g[alan], list), alan
    # Tekil bicim OLMAMALI: sunucu onu tanimiyor
    assert "andKelime" not in g


def test_govde_tum_alanlari_tasiyor():
    """Eksik alan sunucuda hataya yol aciyor."""
    g = _bos_govde()
    for alan in ("daire", "esasYil", "kararYil", "baslangicTarihi",
                 "mevzuatNumarasi", "madde", "siralama", "siralamaDirection"):
        assert alan in g, alan


def test_style_govdesi_metne_karismiyor():
    ham = ('<style>.highlight { background-color: yellow; }</style>'
           '<body><p>Danıştay 2. Dairesinin kararı</p></body>')
    m = html_metne(ham)
    assert "background-color" not in m, m
    assert "Danıştay 2. Dairesinin kararı" in m


def test_script_govdesi_metne_karismiyor():
    ham = '<script>var a = 1;</script><p>Karar metni</p>'
    m = html_metne(ham)
    assert "var a" not in m
    assert "Karar metni" in m


def test_captcha_isareti_isi_durduruyor():
    """Captcha cozulmuyor; is duruyor ve insana birakiliyor."""
    import pytest
    with pytest.raises(CaptchaAcik):
        DanistayClient._captcha_denetle('<div id="isDisplayCaptcha">true</div>')


def test_captchasiz_sayfa_gecerli():
    DanistayClient._captcha_denetle('<div id="isDisplayCaptcha">false</div>')


def test_kisa_ad_danistay_diyor():
    from scraper.danistay import DanistayKarari
    k = DanistayKarari(id="1", daire="2. Daire", esas_no="2020/1888",
                       karar_no="2025/6100", karar_tarihi="18.12.2025")
    assert k.kisa_ad == "Danıştay 2. Daire 2020/1888 E. 2025/6100 K."
    assert k.chunk_id == "danistay-1"


def test_api_captcha_mesaji_yakalaniyor():
    """Captcha yalnizca sayfada degil, API cevabinda da bildiriliyor.

    Cekim sirasinda sunucu metadata.FMTE icinde "DisplayCaptcha" dondu.
    Ilk denetimimiz yalnizca sayfa bayragina bakiyordu, bu yuzden sonraki
    anahtarlar sessizce "0 kayit" doneriyordu.
    """
    import pytest
    with pytest.raises(CaptchaAcik):
        DanistayClient._captcha_denetle(
            '{"data":null,"metadata":{"FMTE":"Runtime exception:{0}:DisplayCaptcha"}}')


def test_normal_hata_captcha_sayilmiyor():
    DanistayClient._captcha_denetle(
        '{"data":null,"metadata":{"FMTE":"Lütfen arama kriterlerini giriniz!"}}')
