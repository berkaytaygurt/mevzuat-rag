"""Aibars -- web sunucusu.

Tarayicidaki sayfa Python fonksiyonlarini dogrudan cagiramaz; bu sunucu ikisi
arasindaki koprudur.

Varsayilan olarak yalnizca kendi makinende dinler (127.0.0.1). Baskasinin
erisebilmesi icin .env icinde HOST=0.0.0.0 yapilir; o durumda AIBARS_KULLANICI
ve AIBARS_SIFRE tanimlanmadan sunucu acilmaz -- sifresiz bir servisi aga acmak
hem Gemini kotasini hem makineyi savunmasiz birakir.

Calistirmak icin:
    .venv\Scripts\python server.py
Sonra tarayicida: http://localhost:8000
"""
from __future__ import annotations

import logging
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("aibars")

WEB = Path(__file__).parent / "web"

_basic = HTTPBasic(auto_error=False)


def kimlik(kimlik_bilgisi: HTTPBasicCredentials | None = Depends(_basic)) -> str:
    """Sifre tanimliysa dogrular. Tanimli degilse (yerel kullanim) serbest birakir."""
    if not config.SIFRE:
        return "yerel"
    if kimlik_bilgisi is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Giris gerekli",
                            headers={"WWW-Authenticate": "Basic"})
    # compare_digest: dogru/yanlis karsilastirmasinin suresi sizmasin diye
    kullanici_ok = secrets.compare_digest(kimlik_bilgisi.username, config.KULLANICI)
    sifre_ok = secrets.compare_digest(kimlik_bilgisi.password, config.SIFRE)
    if not (kullanici_ok and sifre_ok):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kullanici adi veya sifre hatali",
                            headers={"WWW-Authenticate": "Basic"})
    return kimlik_bilgisi.username


app = FastAPI(title="Aibars", dependencies=[Depends(kimlik)])

_kaynaklar: dict = {}


def kaynaklar():
    """Model ve indeksi ilk istekte yukler, sonra bellekte tutar."""
    if not _kaynaklar:
        from core.embedder import Embedder
        from core.generate import Generator
        from core.retrieve import Retriever
        from core.vektor import VektorDeposu

        log.info("indeks ve model yukleniyor...")
        store = VektorDeposu()
        emb = Embedder()
        _kaynaklar["store"] = store
        _kaynaklar["retriever"] = Retriever(store, emb)
        _kaynaklar["generator"] = Generator()

        # Karar indeksi istege bagli: yoksa ya da bozuksa site mevzuatla
        # calismaya devam eder. Kararlar burada bir ek, onkosul degil.
        _kaynaklar["karar"] = None
        try:
            from core.karar_ara import KararArayici
            ka = KararArayici(emb, reranker=_kaynaklar["retriever"].reranker)
            if ka.hazir_mi():
                _kaynaklar["karar"] = ka
                log.info("karar indeksi bulundu: %d parca", ka.store.sayi())
        except Exception as exc:
            log.warning("karar indeksi yuklenemedi, mevzuatla devam: %s", exc)

        log.info("hazir: %d madde", store.sayi())
    return _kaynaklar


# mevzuat.gov.tr'deki tur kodlari; payload'da tur adi saklaniyor
_TUR_KODU = {ad: no for no, ad in config.MEVZUAT_TURLERI.items()}


def resmi_url(m: dict) -> str:
    """Maddenin ait oldugu mevzuatin resmi sayfasi.

    Kullanicinin cevabi kaynagindan dogrulayabilmesi icin: "bana guvenme,
    devletin sitesinde kendin oku". Madde bazinda derin baglanti yok, mevzuat
    sayfasina gidiyoruz.
    """
    no = m.get("mevzuat_no")
    tertip = m.get("tertip")
    tur = _TUR_KODU.get(m.get("mevzuat_tur", ""), 1)
    if not (no and tertip):
        return ""
    return (f"{config.BASE_URL}/mevzuat?MevzuatNo={no}"
            f"&MevzuatTur={tur}&MevzuatTertip={tertip}")


class Soru(BaseModel):
    soru: str
    # Olculdu: LLM'e 5 madde gonderince dogru madde %82 oraninda baglamda
    # oluyor, 10 gonderince %91. Ek maliyet yok cunku yeniden siralayici
    # zaten 25 adayi puanliyor; 15'e cikarmak bir sey kazandirmiyor.
    k: int = 10
    mulga_haric: bool = True
    cevap_uret: bool = True


@app.get("/api/durum")
def durum():
    try:
        k = kaynaklar()
        return {"hazir": True, "madde_sayisi": k["store"].sayi(),
                "saglayici": config.PROVIDER,
                "embed_model": config.EMBED_MODEL.split("/")[-1]}
    except Exception as exc:
        return JSONResponse({"hazir": False, "hata": str(exc)}, status_code=503)


@app.post("/api/sor")
def sor(istek: Soru):
    if not istek.soru.strip():
        return JSONResponse({"hata": "Soru bos"}, status_code=400)

    k = kaynaklar()
    maddeler = k["retriever"].ara(istek.soru, limit=istek.k,
                                 mulga_haric=istek.mulga_haric)

    kararlar = []
    if k.get("karar") is not None:
        try:
            kararlar = k["karar"].ara(istek.soru, limit=3)
        except Exception as exc:      # karar tarafi cevabi engellememeli
            log.warning("karar aramasi basarisiz: %s", exc)

    cevap, cevap_hatasi = None, None
    if istek.cevap_uret and maddeler:
        try:
            cevap = k["generator"].cevapla(istek.soru, maddeler, kararlar)
        except Exception as exc:
            cevap_hatasi = str(exc)
            log.warning("cevap uretilemedi: %s", exc)

    return {
        "soru": istek.soru,
        "cevap": cevap,
        "cevap_hatasi": cevap_hatasi,
        "maddeler": [{
            "mevzuat_adi": m.get("mevzuat_adi", ""),
            "mevzuat_no": m.get("mevzuat_no", ""),
            "madde_no": m.get("madde_no", ""),
            "baslik": m.get("baslik", ""),
            "bolum": m.get("bolum", ""),
            "metin": m.get("metin", ""),
            "mulga": m.get("mulga", False),
            "kismi_mulga": m.get("kismi_mulga", False),
            "skor": round(m.get("skor", 0), 4),
            "kaynaklar": m.get("kaynaklar", []),
            "resmi_url": resmi_url(m),
        } for m in maddeler],
        "kararlar": [{
            "kisa_ad": kr.get("kisa_ad", ""),
            "daire": kr.get("daire", ""),
            "esas_no": kr.get("esas_no", ""),
            "karar_no": kr.get("karar_no", ""),
            "karar_tarihi": kr.get("karar_tarihi", ""),
            "metin": kr.get("gerekce", ""),
            "skor": round(kr.get("skor", 0), 4),
        } for kr in kararlar],
    }


@app.get("/")
def anasayfa():
    return FileResponse(WEB / "aibars.html")


app.mount("/", StaticFiles(directory=WEB), name="web")


def _guvenlik_kontrolu() -> None:
    """Aga acik sunucuyu sifresiz baslatmaya izin vermez.

    Sifresiz bir Aibars'a linki bulan herkes girer: Gemini kotasi harcanir ve
    makine gereksiz yere disariya acilmis olur. Yerel kullanimda (127.0.0.1)
    sifre istemiyoruz, cunku disaridan zaten erisilemez.
    """
    yerel = config.HOST in ("127.0.0.1", "localhost", "::1")
    if yerel:
        if config.SIFRE:
            log.info("sifre korumasi acik (kullanici: %s)", config.KULLANICI)
        else:
            log.info("yerel mod: yalnizca bu makineden erisilebilir")
        return

    if not (config.KULLANICI and config.SIFRE):
        raise SystemExit(
            f"HOST={config.HOST} ile disariya aciliyorsun ama sifre tanimli degil.\n"
            ".env icine AIBARS_KULLANICI ve AIBARS_SIFRE ekle, ya da\n"
            "HOST=127.0.0.1 yaparak yalnizca kendi makinende calistir."
        )
    log.warning("DIKKAT: sunucu %s uzerinde disariya acik (kullanici: %s)",
                config.HOST, config.KULLANICI)


if __name__ == "__main__":
    import uvicorn

    _guvenlik_kontrolu()

    # Kaynaklari acilista yukluyoruz. Tembel yukleme sunucunun "ayakta" ama
    # calismaz halde durmasina yol aciyordu: Qdrant gomulu modda tek surece
    # izin verdigi icin, oksuz kalmis bir sunucu kilidi tutuyorsa yeni sunucu
    # sorunsuz aciliyor, hata ancak ilk soruda 500 olarak goruluyordu.
    try:
        kaynaklar()
    except Exception as exc:
        raise SystemExit(
            f"Baslatilamadi: {exc}\n\n"
            "Qdrant kilidi hatasiysa baska bir Aibars surecі calisiyor demektir.\n"
            "Once onu kapatin (Gorev Yoneticisi'nde python.exe) ya da:\n"
            "  taskkill /F /IM python.exe"
        )

    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")
