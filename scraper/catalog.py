"""mevzuat.gov.tr'deki mevzuat listesini cikarir.

Site, listeyi POST /anasayfa/MevzuatDatatable uzerinden (DataTables serverSide)
sunuyor. Kimlik dogrulama gerekmiyor. Sayfa sayfa gezip tum kayitlari toplariz.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import config
from .client import MevzuatClient

log = logging.getLogger(__name__)

DATATABLE_URL = f"{config.BASE_URL}/anasayfa/MevzuatDatatable"
# 50'lik sayfalar 100'luklerden daha az hata veriyor.
SAYFA_BOYU = 50


@dataclass
class MevzuatKaydi:
    mevzuat_no: str
    ad: str
    tur: int
    tur_adi: str
    tertip: str
    kabul_tarihi: str = ""
    rg_tarihi: str = ""
    rg_sayisi: str = ""
    # Sunucunun verdigi dogrudan belge adresleri. URL kalibini tahmin etmek
    # yalnizca kanunlarda tutuyor; diger turlerde numaralandirma farkli ve
    # uydurulan adres bos bir "belge bulunamadi" PDF'i donduruyor.
    pdf_url: str = ""
    doc_url: str = ""
    metinsiz: bool = False        # taranmis goruntu, metin katmani yok

    @property
    def iframe_url(self) -> str:
        return (f"{config.BASE_URL}/anasayfa/MevzuatFihristDetayIframe"
                f"?MevzuatTur={self.tur}&MevzuatNo={self.mevzuat_no}"
                f"&MevzuatTertip={self.tertip}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["iframe_url"] = self.iframe_url
        return d


def _tam_url(yol: str | None) -> str:
    """Sunucu bazen goreli yol donduruyor; mutlak adrese cevirir."""
    if not yol:
        return ""
    yol = yol.strip()
    if yol.startswith("http"):
        return yol
    return f"{config.BASE_URL}/{yol.lstrip('/')}"


def _payload(tur: int, start: int, length: int) -> dict:
    return {
        "draw": 1, "start": start, "length": length,
        "columns": [{"data": None, "name": "", "searchable": True,
                     "orderable": False, "search": {"value": "", "regex": False}}
                    for _ in range(3)],
        "order": [], "search": {"value": "", "regex": False},
        "parameters": {"AranacakIfade": "", "AranacakYer": "2",
                       "TamCumle": False, "MevzuatTur": tur, "GenelArama": True},
    }


def listele(client: MevzuatClient, tur: int, limit: int | None = None) -> list[MevzuatKaydi]:
    """Verilen tur icin tum mevzuat kayitlarini dondurur."""
    tur_adi = config.MEVZUAT_TURLERI.get(tur, str(tur))
    kayitlar: list[MevzuatKaydi] = []
    start, toplam = 0, None

    while True:
        # Sunucu arada JSON yerine hata sayfasi donduruyor. Tek denemede
        # cokmek, saatler surecek bir indirmeyi ilk dakikasinda bitiriyordu.
        data = None
        for deneme in range(8):     # gecici hatalar sik; sabirli olmak gerekiyor
            client._throttle()
            try:
                resp = client.session.post(
                    DATATABLE_URL, json=_payload(tur, start, SAYFA_BOYU), timeout=45)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                bekle = min(client.delay * (2 ** deneme), 60)
                log.warning("katalog istegi basarisiz (%s, %d) -> %s; %.0fs bekleniyor",
                            tur_adi, start, str(exc)[:60], bekle)
                time.sleep(bekle)
        if data is None:
            log.error("%s: %d kaydindan sonra vazgecildi", tur_adi, len(kayitlar))
            break

        if toplam is None:
            toplam = data.get("recordsTotal", 0)
            log.info("%s: %d kayit bulundu", tur_adi, toplam)

        satirlar = data.get("data") or []
        if not satirlar:
            break

        for row in satirlar:
            kayitlar.append(MevzuatKaydi(
                mevzuat_no=str(row.get("mevzuatNo", "")).strip(),
                ad=(row.get("mevAdi") or "").strip(),
                tur=tur, tur_adi=tur_adi,
                tertip=str(row.get("mevzuatTertip", "")).strip(),
                kabul_tarihi=row.get("kabulTarih") or "",
                rg_tarihi=row.get("resmiGazeteTarihi") or "",
                rg_sayisi=row.get("resmiGazeteSayisi") or "",
                pdf_url=_tam_url(row.get("pdfUrl")),
                doc_url=_tam_url(row.get("docUrl")),
                metinsiz=bool(row.get("isPlainTextBlank")),
            ))

        start += len(satirlar)
        if limit and len(kayitlar) >= limit:
            return kayitlar[:limit]
        if start >= toplam:
            break

    return kayitlar


def kaydet(kayitlar: list[MevzuatKaydi], yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(
        json.dumps([k.to_dict() for k in kayitlar], ensure_ascii=False, indent=1),
        encoding="utf-8")


def yukle(yol: Path) -> list[MevzuatKaydi]:
    ham = json.loads(yol.read_text(encoding="utf-8"))
    return [MevzuatKaydi(**{k: v for k, v in d.items() if k != "iframe_url"}) for d in ham]
