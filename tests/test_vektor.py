"""Vektor deposu testleri (gecici dizinde calisir, gercek indekse dokunmaz)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.vektor import VektorDeposu  # noqa: E402


def _birim(*bilesenler: float) -> np.ndarray:
    v = np.array(bilesenler, dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def depo(tmp_path):
    kayitlar = [
        {"chunk_id": "a", "mevzuat_no": "4857", "madde_no": "53", "mulga": False},
        {"chunk_id": "b", "mevzuat_no": "4857", "madde_no": "54", "mulga": False},
        {"chunk_id": "c", "mevzuat_no": "6098", "madde_no": "1", "mulga": True},
    ]
    vekt = np.vstack([_birim(1, 0, 0), _birim(0, 1, 0), _birim(1, 0.05, 0)])
    d = VektorDeposu(yol=tmp_path)
    d.kaydet(kayitlar, vekt)
    return d


def test_en_yakin_kayit_ilk_sirada(depo):
    sonuc = depo.search(_birim(1, 0, 0), limit=2, mulga_haric=False)
    assert sonuc[0]["chunk_id"] == "a"
    assert sonuc[0]["skor"] > sonuc[1]["skor"]


def test_mulga_varsayilan_olarak_elenir(depo):
    """Mulga madde, yururlukteki gibi sunulursa en tehlikeli hata turu."""
    idler = [k["chunk_id"] for k in depo.search(_birim(1, 0, 0), limit=3)]
    assert "c" not in idler


def test_mulga_haric_kapatilinca_gelir(depo):
    idler = [k["chunk_id"] for k in depo.search(_birim(1, 0, 0), limit=3,
                                                mulga_haric=False)]
    assert "c" in idler


def test_mevzuat_no_filtresi(depo):
    sonuc = depo.search(_birim(1, 0, 0), limit=5, mevzuat_no="6098",
                        mulga_haric=False)
    assert [k["chunk_id"] for k in sonuc] == ["c"]


def test_limit_kayit_sayisini_asamaz(depo):
    assert len(depo.search(_birim(1, 0, 0), limit=99, mulga_haric=False)) == 3


def test_sayi_ve_kayitlar(depo):
    assert depo.sayi() == 3
    assert len(depo.tum_kayitlar()) == 3


def test_uyumsuz_uzunluk_hata_verir(tmp_path):
    """Kayit ve vektor sayisi ayrilirsa siralama sessizce yanlis olur."""
    with pytest.raises(ValueError):
        VektorDeposu(yol=tmp_path).kaydet([{"chunk_id": "a"}], np.zeros((2, 3), np.float32))


def test_depo_yoksa_acik_hata(tmp_path):
    with pytest.raises(FileNotFoundError):
        VektorDeposu(yol=tmp_path / "yok").sayi()
