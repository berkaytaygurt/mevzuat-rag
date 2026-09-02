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
        # Atif zinciri: hangi karar hangi maddeyi yorumlamis. Kararlarin
        # kendi metninden otomatik cikarildi; ticari veri tabanlari bu
        # baglantiyi elle kuruyor.
        _kaynaklar["zincir"] = None
        try:
            from core.atif_zinciri import AtifZinciri
            z = AtifZinciri()
            if z.hazir_mi():
                _kaynaklar["zincir"] = z
                log.info("atif zinciri bulundu: %d madde", z.sayi())
        except Exception as exc:
            log.warning("atif zinciri yuklenemedi: %s", exc)

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
    karsi_taraf: bool = True
    vurgu: bool | None = None




@app.get("/api/durum")
def durum():
    try:
        k = kaynaklar()
        return {"hazir": True, "madde_sayisi": k["store"].sayi(),
                "saglayici": config.PROVIDER,
                "embed_model": config.EMBED_MODEL.split("/")[-1]}
    except Exception as exc:
        return JSONResponse({"hazir": False, "hata": str(exc)}, status_code=503)


class Netlestirme(BaseModel):
    soru: str


@app.post("/api/netlestir")
def netlestir(istek: Netlestirme):
    """Olay anlatimini secilebilir hukuki mesele basliklarina cevirir.

    NEDEN VAR
    Olculdu -- ayni mesele dort ayri bicimde soruldugunda, bes hukuk alaninda:

        olay anlatimi (uzun, olgulu)   1. sirada 1/5   MRR 0,30
        dogal soru cumlesi             1. sirada 4/5   MRR 0,83
        hukuki kavram (kisa)           1. sirada 5/5   MRR 1,00

    Yani sistem, avukatin en dogal yazma bicimi olan olay anlatiminda
    caliskan degil. Ama avukattan "kavram gibi yaz" diye beklemek de dogru
    degil; o ne istedigini bilir, nasil ifade edecegini bilmez.

    Bu uc nokta o farki kapatiyor: olay anlatimi mesele basliklarina
    cevriliyor, kullanici hangisini sordugunu SECIYOR, arama secilen
    baslikla yapiliyor. Yani sistem tahmin etmiyor, soruyor.

    Basliklar kulliyata yakinligina gore siralanir: karsiligi olmayan
    baslik once gosterilmemeli.
    """
    soru = istek.soru.strip()
    if not soru:
        return {"gerekli": False, "meseleler": []}

    from core.mesele import cok_olgulu_mu, meseleleri_ayir

    # Kisa ve net sorguda netlestirme gereksiz; kullaniciyi yormamali.
    if not cok_olgulu_mu(soru):
        return {"gerekli": False, "meseleler": []}

    k = kaynaklar()
    try:
        basliklar = meseleleri_ayir(soru, k["generator"])
    except Exception as exc:
        log.warning("netlestirme basarisiz: %s", str(exc)[:80])
        return {"gerekli": False, "meseleler": []}
    if len(basliklar) < 2:
        return {"gerekli": False, "meseleler": []}

    # Her baslik icin kulliyattaki en yakin maddenin HAM benzerligi. Yeniden
    # siralayicinin puani bu is icin kullanilamaz: o aday havuzu icinde
    # siralama yapar ve havuzda hep bir en iyi vardir.
    puanli = []
    for baslik in basliklar:
        try:
            puan = k["retriever"]._ham_benzerlik(baslik)
        except Exception:
            puan = 0.0
        puanli.append({"baslik": baslik, "puan": round(float(puan), 3)})
    puanli.sort(key=lambda x: x["puan"], reverse=True)
    return {"gerekli": True, "meseleler": puanli}


def vurgu_parcalari(metin: str, soru: str, kaynak: dict) -> list[dict]:
    """Madde metnini parcalara bolup ilgili olani isaretler.

    Hata durumunda tek parca doner: vurgu bir kolaylik, cevabi engellememeli.
    """
    if not metin:
        return []
    try:
        from core.vurgu import parcalari_hazirla

        return parcalari_hazirla(metin, soru, kaynak["retriever"].reranker)
    except Exception as exc:
        log.debug("vurgu hesaplanamadi: %s", exc)
        return [{"metin": metin, "vurgu": False}]


@app.post("/api/sor")
def sor(istek: Soru):
    if not istek.soru.strip():
        return JSONResponse({"hata": "Soru bos"}, status_code=400)

    k = kaynaklar()
    maddeler = k["retriever"].ara(istek.soru, limit=istek.k,
                                 mulga_haric=istek.mulga_haric)

    # Sorgunun nasil anlasildigi: kullaniciya "seni soyle anladim" demek icin
    anlasilan = getattr(k["retriever"], "son_genisletme", None)

    # Guven: en iyi HAM vektor benzerligi esigin altindaysa soru kulliyatla
    # ilgisiz demektir. Yeniden siralayicinin puani bu is icin kullanilamaz
    # (aday havuzu icinde siralama yapar, havuzda hep bir en iyi vardir).
    vektor_puani = getattr(k["retriever"], "son_vektor_puani", 0.0)
    guven_dusuk = vektor_puani < config.GUVEN_ESIGI

    kararlar = []
    if k.get("karar") is not None:
        try:
            kararlar = k["karar"].ara(istek.soru, limit=3)
        except Exception as exc:      # karar tarafi cevabi engellememeli
            log.warning("karar aramasi basarisiz: %s", exc)

    # Karsi tarafin dayanabilecegi maddeler. Tavsiye degil, yalnizca
    # "bunlara da bak" listesi -- cikarim kullanicinin.
    karsi_sorgu, karsi_maddeler = "", []
    if istek.karsi_taraf and maddeler and not guven_dusuk:
        try:
            from core.karsi_taraf import karsi_maddeler as _karsi
            karsi_sorgu, karsi_maddeler = _karsi(
                istek.soru, k["retriever"], k["generator"],
                limit=5, asil_maddeler=maddeler)
        except Exception as exc:
            log.warning("karsi taraf aramasi basarisiz: %s", str(exc)[:80])

    cevap, cevap_hatasi, dogrulama = None, None, None
    if guven_dusuk:
        # Alakasiz soruda cevap uretmek, modelin eldeki maddelerden bir sey
        # uydurmasina yol aciyor. Uretimi hic baslatmiyoruz.
        cevap = ("Bu soru için külliyatta yeterince ilgili bir düzenleme "
                 "bulamadım. Aşağıdaki maddeler en yakın eşleşmeler ama "
                 "sorunuzu karşılamayabilir.")
    elif istek.cevap_uret and maddeler:
        try:
            cevap = k["generator"].cevapla(istek.soru, maddeler, kararlar)
            dogrulama = getattr(k["generator"], "son_dogrulama", None)
        except Exception as exc:
            cevap_hatasi = str(exc)
            log.warning("cevap uretilemedi: %s", exc)

    return {
        "soru": istek.soru,
        "cevap": cevap,
        "cevap_hatasi": cevap_hatasi,
        "dogrulama": dogrulama,
        "anlasilan": anlasilan,
        "karsi_taraf": {
            "sorgu": karsi_sorgu,
            "maddeler": [{
                "mevzuat_adi": m.get("mevzuat_adi", ""),
                "mevzuat_no": m.get("mevzuat_no", ""),
                "madde_no": m.get("madde_no", ""),
                "baslik": m.get("baslik", ""),
                "metin": m.get("metin", ""),
                "resmi_url": resmi_url(m),
                "yorumlayan_kararlar": (
                    k["zincir"].kararlar(m.get("mevzuat_no", ""),
                                         str(m.get("madde_no", "")))
                    if k.get("zincir") else []),
            } for m in karsi_maddeler],
        },
        "guven": {"puan": round(vektor_puani, 3),
                  "esik": config.GUVEN_ESIGI,
                  "dusuk": guven_dusuk},
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
            "yorumlayan_kararlar": (
                k["zincir"].kararlar(m.get("mevzuat_no", ""),
                                     str(m.get("madde_no", "")))
                if k.get("zincir") else []),
            # Metin parcalari + hangisinin soruyla ilgili oldugu. Vurgu
            # yalnizca EMIN oldugunda konuluyor: yanlis yeri isaretlemek,
            # hic isaretlememekten kotu -- kullanici isaretli yeri okuyup
            # dogru kismi atlar.
            "parcalar": (
                vurgu_parcalari(m.get("metin", ""), istek.soru, k)
                if (istek.vurgu if istek.vurgu is not None else config.VURGU)
                else []),
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
