"""Olcum gunlugu: varsayilan kapali, acikken yaziyor, asla cevabi bozmuyor."""
import json

import config
import server


def test_varsayilan_kapali():
    assert config.METRIK is False, "olcum gunlugu varsayilan acik olmamali"


def test_kapaliyken_dosya_olusmuyor(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "METRIK", False)
    monkeypatch.setattr(config, "METRIK_YOLU", tmp_path / "m.jsonl")
    server.metrik_yaz("soru", 0.0, [], 0.5, False, 0, True)
    assert not (tmp_path / "m.jsonl").exists()


def test_acikken_satir_yaziyor(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(config, "METRIK", True)
    monkeypatch.setattr(config, "METRIK_YOLU", tmp_path / "m.jsonl")
    maddeler = [{"mevzuat_no": "4857", "madde_no": "19"}]
    server.metrik_yaz("test sorusu", time.time() - 1.5, maddeler, 0.72, False, 3, True)
    satir = json.loads((tmp_path / "m.jsonl").read_text(encoding="utf-8").strip())
    assert satir["soru"] == "test sorusu"
    assert satir["ilk"] == "4857 m.19"
    assert satir["sure"] >= 1.4
    assert satir["guven"] == 0.72


def test_hata_cevabi_engellemiyor(monkeypatch):
    """Olcum bir kolaylik; yazilamazsa sessizce gecilmeli."""
    monkeypatch.setattr(config, "METRIK", True)
    monkeypatch.setattr(config, "METRIK_YOLU", None)      # kasitli bozuk
    server.metrik_yaz("soru", 0.0, [], 0.5, False, 0, True)   # istisna atmamali
