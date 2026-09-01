"""Gemini harcamasina sert tavan.

Neden var: ucretsiz katmanda soru uretirken art arda istek atip gunluk kotayi
tuketmistim. Ucretli katmanda ayni hata para demek. Bu modul, kod tarafinda
durduran bir duvar koyar -- Google'in butce uyarisi yalnizca haber verir,
durdurmaz.

Sayac diske yaziliyor: surec yeniden baslasa da gunluk toplam korunur.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import date
from pathlib import Path

import config

log = logging.getLogger(__name__)

SAYAC_YOLU = config.ROOT / "data" / "gemini_sayac.json"
_kilit = threading.Lock()

# Gemini Flash fiyati (1M token basina, ABD dolari). Kaba tahmin icin;
# fatura degil, buyukluk hissi vermek amacli.
GIRDI_1M = 0.30
CIKTI_1M = 2.50


def _oku() -> dict:
    if not SAYAC_YOLU.exists():
        return {}
    try:
        return json.loads(SAYAC_YOLU.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _yaz(veri: dict) -> None:
    SAYAC_YOLU.parent.mkdir(parents=True, exist_ok=True)
    SAYAC_YOLU.write_text(json.dumps(veri, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def bugun() -> dict:
    veri = _oku()
    g = date.today().isoformat()
    if veri.get("gun") != g:
        return {"gun": g, "istek": 0, "girdi_token": 0, "cikti_token": 0}
    return veri


class ButceAsildi(RuntimeError):
    """Gunluk istek tavanina ulasildi."""


def izin_iste() -> None:
    """Bir istek yapmadan once cagrilir; tavan asildiysa istisna atar."""
    with _kilit:
        v = bugun()
        if v["istek"] >= config.GEMINI_GUNLUK_SINIR:
            raise ButceAsildi(
                f"Gunluk Gemini siniri doldu ({v['istek']}/"
                f"{config.GEMINI_GUNLUK_SINIR}). Sinir config.GEMINI_GUNLUK_SINIR "
                f"ile degistirilebilir.")


def kaydet(girdi_token: int = 0, cikti_token: int = 0) -> None:
    """Basarili bir istegi sayaca isler."""
    with _kilit:
        v = bugun()
        v["istek"] += 1
        v["girdi_token"] += int(girdi_token or 0)
        v["cikti_token"] += int(cikti_token or 0)
        _yaz(v)
        if v["istek"] % 100 == 0:
            log.info("Gemini: bugun %d istek, tahmini %.2f USD",
                     v["istek"], tahmini_maliyet(v))


def tahmini_maliyet(v: dict | None = None) -> float:
    v = v or bugun()
    return (v.get("girdi_token", 0) / 1e6 * GIRDI_1M
            + v.get("cikti_token", 0) / 1e6 * CIKTI_1M)


def durum() -> str:
    v = bugun()
    return (f"bugun {v['istek']}/{config.GEMINI_GUNLUK_SINIR} istek, "
            f"~{tahmini_maliyet(v):.3f} USD")


def toplu_is_onayi(adet: int, ortalama_girdi: int = 1500,
                   ortalama_cikti: int = 100) -> str:
    """Toplu bir is baslamadan once tahmini maliyeti metin olarak doner."""
    usd = (adet * ortalama_girdi / 1e6 * GIRDI_1M
           + adet * ortalama_cikti / 1e6 * CIKTI_1M)
    return (f"{adet} istek yapilacak, tahmini maliyet ~{usd:.2f} USD "
            f"(~{usd * 42:.0f} TL). {durum()}")
