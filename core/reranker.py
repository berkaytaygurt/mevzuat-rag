"""Yeniden siralama (cross-encoder).

Arama iki asamali calisir:

  1. Hizli aday toplama -- vektor + BM25 + madde numarasi. Bu asama sorguyu ve
     belgeyi AYRI AYRI vektore cevirir; hizlidir ama aralarindaki iliskiyi
     yalnizca kaba bir benzerlikle olcer.
  2. Yeniden siralama -- cross-encoder sorgu ile madde metnini BIRLIKTE okur ve
     "bu madde bu soruya cevap veriyor mu" diye puanlar. Yavastir, bu yuzden
     yalnizca ilk asamanin getirdigi 20-30 aday uzerinde calisir.

Neden gerekli: 33.742 maddelik kulliyatta ayni kelimeler onlarca kanunda
geciyor. "Hirsizlik sucunun cezasi" sorusunda ilk asama TCK m.147'yi
(Zorunluluk hali) m.141'in (Hirsizlik) onune koyabiliyordu; iki madde de ayni
bolumde ve benzer kelimeler tasiyor. Cross-encoder soruyu okudugu icin bu ayrimi
yapabiliyor.
"""
from __future__ import annotations

import logging

import config

log = logging.getLogger(__name__)


def _olcekle(degerler: list[float]) -> list[float]:
    """Puanlari 0-1 arasina ceker (min-max).

    Cross-encoder puani ile RRF puani cok farkli olceklerde; dogrudan
    toplamak buyuk olcekli olanin digerini ezmesi demek olurdu.
    """
    if not degerler:
        return []
    en_az, en_cok = min(degerler), max(degerler)
    if en_cok - en_az < 1e-9:
        return [0.5] * len(degerler)
    return [(d - en_az) / (en_cok - en_az) for d in degerler]


def _ikincil_madde(kayit: dict) -> bool:
    """Ek / Gecici / Mukerrer madde mi?"""
    no = str(kayit.get("madde_no", ""))
    return no[:1].isalpha()          # "Ek 3", "Geçici 7", "Mükerrer 5"


# Normlar hiyerarsisi: ustteki norm alttakini baglar. Ayni konuda hem kanun
# hem yonetmelik eslesirse kanun onceliklidir -- hukuken de boyle.
#
# Kulliyat 33 binden 174 bine cikinca olculdu: "yillik izin" gibi bir soru
# artik yuzlerce kurum yonetmeligiyle yarisiyor ve MRR 0.751'den 0.649'a
# dustu. Hiyerarsi bilgisi bu yarismayi dogru tarafa cozer.
_HIYERARSI = {
    "Kanun": 1.00,
    "Cumhurbaskanligi Kararnamesi": 0.97,
    "Kanun Hukmunde Kararname": 0.97,
    "Tuzuk": 0.94,
    "Cumhurbaskanligi Yonetmeligi": 0.91,
    "Yonetmelik": 0.91,
    "Kurum ve Kurulus Yonetmeligi": 0.88,
    "Teblig": 0.85,
}


def _hiyerarsi_carpani(kayit: dict) -> float:
    return _HIYERARSI.get(kayit.get("mevzuat_tur", ""), 0.90)


class Reranker:
    def __init__(self, model_adi: str | None = None, device: str | None = None,
                 batch: int | None = None, max_uzunluk: int | None = None):
        self.model_adi = model_adi or config.RERANK_MODEL
        self.device = device or config.EMBED_DEVICE
        self.batch = batch or config.RERANK_BATCH
        self.max_uzunluk = max_uzunluk or config.RERANK_MAX_SEQ
        self._model = None

    @property
    def model(self):
        if self._model is None:
            import torch
            from sentence_transformers import CrossEncoder

            if self.device == "cuda" and not torch.cuda.is_available():
                log.warning("CUDA yok, yeniden siralama CPU'da calisacak")
                self.device = "cpu"

            log.info("yeniden siralayici yukleniyor: %s (%s)", self.model_adi, self.device)
            self._model = CrossEncoder(
                self.model_adi, device=self.device, max_length=self.max_uzunluk,
                model_kwargs={"torch_dtype": torch.float16} if self.device == "cuda" else {},
            )
            if self.device == "cuda":
                bos, _ = torch.cuda.mem_get_info()
                log.info("yukleme sonrasi bos VRAM: %.1f GB", bos / 1e9)
        return self._model

    @staticmethod
    def _madde_metni(k: dict) -> str:
        """Cross-encoder'a verilecek metin. Kanun adi ve baslik da dahil:
        madde govdesi cogu zaman konuyu tekrar etmiyor ("Ondort gunden az
        olamaz" cumlesi tek basina neyin izni oldugunu soylemiyor)."""
        parcalar = [
            k.get("mevzuat_adi", ""),
            f"Madde {k.get('madde_no', '')}",
            k.get("baslik", ""),
            k.get("metin", ""),
        ]
        return " | ".join(p for p in parcalar if p)

    def sirala(self, soru: str, adaylar: list[dict], limit: int) -> list[dict]:
        if len(adaylar) <= 1:
            return adaylar[:limit]

        # Kullanicilar sorguyu genelde Turkce karakter kullanmadan yazar.
        # Cross-encoder ham metni aldigi icin "hirsizlik" ile "hırsızlık"
        # arasindaki farka takiliyordu: aksanli sorguda TMK m.124 birinci
        # sirada gelirken ayni sorunun ASCII yazimi m.129'u one cikariyordu.
        # Iki tarafi da ayni sekilde katlayarak bu farki kaldiriyoruz.
        if config.RERANK_KATLA:
            from .retrieve import _tr_katla

            hazirla = _tr_katla
        else:
            def hazirla(x: str) -> str:
                return x

        ciftler = [(hazirla(soru), hazirla(self._madde_metni(k))) for k in adaylar]
        ce_puan = self.model.predict(ciftler, batch_size=self.batch,
                                     show_progress_bar=False)

        # Birinci asamanin RRF puanini tamamen atmak bilgi kaybi: madde
        # numarasi eslesmesi ve BM25 orada hesaplanmis durumda. Iki sinyali
        # birlestiriyoruz. Iki puan farkli olceklerde oldugu icin once her
        # birini kendi icinde 0-1 arasina cekiyoruz.
        rrf_puan = [k.get("skor", 0.0) for k in adaylar]
        ce_n = _olcekle([float(p) for p in ce_puan])
        rrf_n = _olcekle(rrf_puan)
        w = config.RERANK_AGIRLIK
        birlesik = [w * c + (1 - w) * r for c, r in zip(ce_n, rrf_n)]

        # Ek / Gecici maddeler kucuk bir ceza alir. Bunlar sonradan eklenmis
        # ya da gecis donemine ozgu hukumlerdir; bir konunun ASIL duzenlemesi
        # nadiren orada olur. Olculen hatalarda bu kalip goruldu: "fazla
        # calisma ucreti" sorgusu Is Kanunu m.41 yerine Vergi Usul Kanunu
        # Ek 13'u one cikariyordu -- baslik birebir ayni ama madde ikincil.
        if config.EK_MADDE_CEZASI:
            birlesik = [b - config.EK_MADDE_CEZASI if _ikincil_madde(k) else b
                        for b, k in zip(birlesik, adaylar)]

        # Normlar hiyerarsisi: kanun, yonetmelikten oncelikli.
        if config.HIYERARSI:
            birlesik = [b * _hiyerarsi_carpani(k)
                        for b, k in zip(birlesik, adaylar)]

        sirali = sorted(zip(adaylar, birlesik, ce_puan),
                        key=lambda x: x[1], reverse=True)
        return [{**k, "skor": float(b), "ce_skor": float(c),
                 "yeniden_siralandi": True}
                for k, b, c in sirali[:limit]]
