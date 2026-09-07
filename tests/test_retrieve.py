"""Arama katmani testleri (ag ve GPU gerektirmez)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.retrieve import (  # noqa: E402
    KISALTMALAR, MADDE_REF_RE, Retriever, _tr_katla,
)


# --------------------------------------------------------------------------
# Turkce karakter katlama
# --------------------------------------------------------------------------
@pytest.mark.parametrize("girdi,beklenen", [
    ("Kişisel Verilerin İşlenme Şartları", "kisisel verilerin islenme sartlari"),
    ("Yıllık Ücretli İzin", "yillik ucretli izin"),
    ("Çoğunluk", "cogunluk"),
    ("İŞ KANUNU", "is kanunu"),
])
def test_tr_katlama(girdi, beklenen):
    assert _tr_katla(girdi) == beklenen


def test_aksansiz_sorgu_aksanli_metinle_eslesir():
    """Kullanicilar sorguyu genelde Turkce karakter kullanmadan yazar.

    Katlama olmadan 'kisisel' ile 'kişisel' ayri token sayiliyor ve birebir
    baslik eslesmesi olan madde hic getirilemiyordu.
    """
    belge = Retriever._tokenize("Kişisel verilerin işlenme şartları")
    sorgu = Retriever._tokenize("kisisel verilerin islenme sartlari")
    assert belge == sorgu


def test_katlama_kelimeleri_birlestirmez():
    assert _tr_katla("şart") != _tr_katla("kart")


# --------------------------------------------------------------------------
# Baslik agirliklandirma
# --------------------------------------------------------------------------
def test_baslik_bm25_metninde_tekrarlanir():
    """Uzun govde metni basligi seyreltiyordu; baslik uc kez gecmeli."""
    kayit = {"mevzuat_adi": "TEST KANUNU", "baslik": "Benzersizbaslik",
             "madde_no": "5", "metin": "govde " * 200}
    metin = Retriever._kayit_metni(kayit)
    assert metin.lower().count("benzersizbaslik") == 3


# --------------------------------------------------------------------------
# Madde numarasi referansi
# --------------------------------------------------------------------------
@pytest.mark.parametrize("soru,beklenen", [
    ("TBK 6. madde ne diyor", "6"),
    ("madde 53 nedir", "53"),
    ("İş Kanunu m. 25", "25"),
    ("4857 sayılı kanun madde 18", "18"),
])
def test_madde_referansi_yakalanir(soru, beklenen):
    # MADDE_REF_RE artik adli gruplar kullaniyor; "geçici"/"ek" oneki ve
    # "3/A" gibi harf ekleri de yakalandigi icin konum numaralari degisti.
    m = MADDE_REF_RE.search(soru)
    assert m is not None
    assert (m.group("no1") or m.group("no2")) == beklenen


def test_kisaltmalar_dogru_kanuna_isaret_eder():
    assert KISALTMALAR["tbk"] == "6098"
    assert KISALTMALAR["tmk"] == "4721"
    assert KISALTMALAR["kvkk"] == "6698"


# --------------------------------------------------------------------
# HyDE + ham soru fuzyonu
# --------------------------------------------------------------------
def test_hyde_ham_fuzyonu_acik():
    """HyDE uretilen metin sorunun KONUSUNU dusurebiliyor.

    "uyusturucu madde ticareti sucunda etkin pismanlik" sorusunda
    uretilen hukumde "uyusturucu" gecmiyordu; TCK'da "Etkin pismanlik"
    baslikli 11 madde var ve dogrusu (m.192) ilk 20'ye bile girmiyordu --
    sistem "dayanak bulamadim" diyordu.

    Cozum ham soruyu AYRI BIR SINYAL olarak RRF'e katmak. Olculdu:

        agirlik 0,0   MRR 0,951   ilk20 33/34   m.192 bulunamadi
        agirlik 1,0   MRR 0,931   ilk20 34/34   m.192 1. sirada

    MRR dusuyor ama hicbir soru kaybolmuyor. Cevabi ureten model ilk 10
    maddeyi gordugu icin siradan cok VARLIK onemli.

    Daha once denenen ve GERILETTIGI ICIN ALINMAYAN iki yol:
    metinleri birlestirmek ve isteme "konuyu koru" kurali eklemek.
    """
    import config

    assert config.HYDE_HAM_AGIRLIK > 0, "fuzyon kapatilmis"
