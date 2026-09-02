"""Artimli indekslemenin vektorleri DOGRU kayda esledigini denetler.

NEDEN VAR
275 bin maddeyi bastan gommek RTX 3050'de ~6.8 saat suruyor; artimli yolda
degismeyen maddenin vektoru onceki indeksten aliniyor (olculdu: dipnot
duzeltmesinden sonra 252.541 madde yeniden kullanildi, 23.350'si gomuldu,
sure 35 dakikaya indi).

Bu yolun hatasi SESSIZDIR: yanlis satir esleniirse arama calismaya devam
eder ama sonuclar sacmalar. Bu yuzden esleme testle sabitlendi.
"""
import json

import numpy as np
import pytest

import cli
import config


@pytest.fixture
def indeks(tmp_path, monkeypatch):
    kayitlar = [
        {"mevzuat_adi": "A Kanunu", "madde_no": "1", "baslik": "", "metin": "birinci"},
        {"mevzuat_adi": "A Kanunu", "madde_no": "2", "baslik": "", "metin": "ikinci"},
        {"mevzuat_adi": "B Kanunu", "madde_no": "1", "baslik": "", "metin": "ucuncu"},
    ]
    vektorler = np.array([[1., 0.], [0., 1.], [.5, .5]], dtype=np.float32)
    (tmp_path / "kayitlar.json").write_text(json.dumps(kayitlar), encoding="utf-8")
    np.save(tmp_path / "vektorler.npy", vektorler)
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    return kayitlar, vektorler


def test_degismeyen_madde_dogru_vektoru_aliyor(indeks):
    kayitlar, vektorler = indeks
    # Sira KASITLI olarak degistirildi: esleme sıraya degil metne dayanmali
    metinler = [cli._embed_metni(kayitlar[2]),
                cli._embed_metni(kayitlar[0]),
                "A Kanunu\nMadde 3\nbambaska bir metin"]
    satirlar, maske = cli._onceki_vektorler(metinler)
    assert list(maske) == [True, True, False]
    assert np.allclose(satirlar[0], vektorler[2])
    assert np.allclose(satirlar[1], vektorler[0])
    assert np.allclose(satirlar[2], 0)          # gomulecek satir bos birakilir


def test_degisen_madde_yeniden_gomuluyor(indeks):
    kayitlar, _ = indeks
    degisik = dict(kayitlar[1], metin="ikinci fikra eklendi")
    satirlar, maske = cli._onceki_vektorler([cli._embed_metni(degisik)])
    assert list(maske) == [False], "metin degistigi halde eski vektor kullanildi"


def test_onceki_indeks_yoksa_tam_gomme(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    assert cli._onceki_vektorler(["herhangi"]) == (None, None)


def test_tutarsiz_indeks_reddediliyor(tmp_path, monkeypatch):
    (tmp_path / "kayitlar.json").write_text(json.dumps([{"metin": "a"}]),
                                            encoding="utf-8")
    np.save(tmp_path / "vektorler.npy", np.zeros((5, 2), dtype=np.float32))
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    assert cli._onceki_vektorler(["a"]) == (None, None)
