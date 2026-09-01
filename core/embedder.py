"""Lokal GPU embedding katmani (Qwen3-Embedding-0.6B).

Qwen3-Embedding, sorgu tarafinda bir gorev talimati bekler; dokuman tarafinda
beklemez. Bu asimetri retrieval isabetini belirgin sekilde artirir -- Gemini'nin
task_type parametresiyle ayni mantik. Bu yuzden encode_documents ve encode_query
ayri fonksiyonlardir; ikisini karistirmak sessizce kaliteyi dusurur.
"""
from __future__ import annotations

import logging

import config

log = logging.getLogger(__name__)

# Kirpma ve gomme parca boyutlari. Tum kulliyati tek hamlede islemek
# 15 GB RAM'i tuketiyordu; parcali islem bellegi sabit tutuyor.
_KIRPMA_PARCASI = 2000
_GOMME_PARCASI = 20000

GOREV = ("Verilen hukuki soruya cevap veren mevzuat maddesini bul")


class Embedder:
    def __init__(self, model_adi: str | None = None, device: str | None = None,
                 batch: int | None = None):
        self.model_adi = model_adi or config.EMBED_MODEL
        self.device = device or config.EMBED_DEVICE
        self.batch = batch or config.EMBED_BATCH
        self.max_seq_length = config.EMBED_MAX_SEQ
        self._model = None

    @property
    def model(self):
        if self._model is None:
            import torch
            from sentence_transformers import SentenceTransformer

            if self.device == "cuda" and not torch.cuda.is_available():
                log.warning("CUDA bulunamadi, CPU'ya duseluyor (cok daha yavas)")
                self.device = "cpu"

            log.info("model yukleniyor: %s (%s)", self.model_adi, self.device)
            self._model = SentenceTransformer(
                self.model_adi,
                device=self.device,
                model_kwargs={"torch_dtype": torch.float16} if self.device == "cuda" else {},
            )
            # Qwen3-Embedding varsayilan olarak 32K baglam acar; 4 GB VRAM'de
            # bu dolu batch'lerde bellek tasmasina yol acar. Maddelerin %99'u
            # 2030 karakterin altinda, 1024 token yalnizca 9 maddeyi kesiyor.
            self._model.max_seq_length = self.max_seq_length

            if self.device == "cuda":
                free, total = torch.cuda.mem_get_info()
                log.info("VRAM: %.1f/%.1f GB bos | max_seq_length=%d",
                         free / 1e9, total / 1e9, self.max_seq_length)
        return self._model

    @property
    def boyut(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def kirp(self, metinler: list[str]) -> list[str]:
        """Metinleri max_seq_length token'a kirpar.

        SentenceTransformer.encode, max_seq_length ayarli olmasina ragmen bu
        modelde kisaltmayi uygulamiyor; 20 bin tokenlik bir maddeyi butun
        haliyle isliyor. Tam kulliyatta en uzun madde 55 bin karakter
        (~21 bin token) ve bu, 4 GB VRAM'i tasirip GPU'yu sistem bellegine
        takas etmeye zorluyordu: batch suresi 0.9 saniyeden 255 saniyeye
        cikiyor, tahmini bitis 30 dakikadan 149 saate firliyordu.
        Kirpmayi encode'a birakmayip kendimiz yapiyoruz.
        """
        # Parca parca isliyoruz. Tum kulliyati (173 bin madde, 147 milyon
        # karakter) tek cagriyla tokenize etmek hem cok yavas hem de token
        # listeleri ve geri cozulen metinler bellekte ayni anda durdugu icin
        # RAM'i tuketiyordu.
        tok = self.model.tokenizer
        cikti: list[str] = []
        for i in range(0, len(metinler), _KIRPMA_PARCASI):
            dilim = metinler[i:i + _KIRPMA_PARCASI]
            idler = tok(dilim, truncation=True, max_length=self.max_seq_length,
                        add_special_tokens=False)["input_ids"]
            cikti.extend(tok.batch_decode(idler, skip_special_tokens=True))
        return cikti

    def encode_documents(self, metinler: list[str], goster: bool = True):
        """Mevzuat maddelerini vektore cevirir. Talimat oneki YOK.

        Kirpma ve gomme is ice gecmis sekilde, parca parca yapilir: aksi
        halde once tum kulliyatin kirpilmis kopyasi bellekte olusuyor.
        """
        import numpy as np

        parcalar = []
        toplam = len(metinler)
        for i in range(0, toplam, _GOMME_PARCASI):
            dilim = metinler[i:i + _GOMME_PARCASI]
            parcalar.append(self.model.encode(
                self.kirp(dilim), batch_size=self.batch,
                normalize_embeddings=True,
                show_progress_bar=goster, convert_to_numpy=True,
            ))
            if toplam > _GOMME_PARCASI:
                log.info("gomme: %d / %d madde", min(i + _GOMME_PARCASI, toplam), toplam)
        return np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]

    def encode_query(self, soru: str | list[str]):
        """Kullanici sorusunu vektore cevirir. Talimat oneki VAR."""
        tekil = isinstance(soru, str)
        sorular = [soru] if tekil else soru
        onekli = [f"Instruct: {GOREV}\nQuery: {s}" for s in sorular]
        vek = self.model.encode(
            self.kirp(onekli), batch_size=self.batch,
            normalize_embeddings=True,
            show_progress_bar=False, convert_to_numpy=True,
        )
        return vek[0] if tekil else vek
