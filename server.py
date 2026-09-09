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

import json
import logging
import os
import re
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
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

        # Madde -> madde atif grafi: kanunun KENDI metnindeki caprazlar.
        # "Bu Kanun, 4 uncu Maddedeki istisnalar disinda ..." diyen bir
        # hukum, m.4'e bakilmadan anlasilmaz; vektor aramasi bu bagi
        # goremiyor. Graf yoksa site grafsiz calismaya devam eder.
        _kaynaklar["graf"] = None
        _kaynaklar["madde_adlari"] = {}
        try:
            from core.atif_grafi import AtifGrafi
            g = AtifGrafi()
            if g.hazir_mi():
                _kaynaklar["graf"] = g
                # "4857-4" avukata bir sey soylemiyor; kanun adi ve madde
                # basligi lazim. Tek seferlik dizin.
                _kaynaklar["madde_adlari"] = {
                    f"{m.get('mevzuat_no')}-{m.get('madde_no')}": (
                        m.get("mevzuat_adi", ""), m.get("baslik", ""))
                    for m in store.tum_kayitlar()}
                log.info("atif grafi bulundu: %d kenar", g.sayi())
        except Exception as exc:
            log.warning("atif grafi yuklenemedi: %s", exc)

        _kaynaklar["karar"] = None
        try:
            from core.karar_ara import KararArayici
            ka = KararArayici(emb, reranker=_kaynaklar["retriever"].reranker)
            if ka.hazir_mi():
                _kaynaklar["karar"] = ka
                log.info("karar indeksi bulundu: %d parca", ka.store.sayi())
        except Exception as exc:
            log.warning("karar indeksi yuklenemedi, mevzuatla devam: %s", exc)

        _kaynaklar["canli_karar"] = None
        if config.CANLI_KARAR:
            try:
                from core.canli_karar import CanliKararArayici
                _kaynaklar["canli_karar"] = CanliKararArayici(
                    _kaynaklar["generator"],
                    reranker=_kaynaklar["retriever"].reranker)
                log.info("canli karar cekimi acik")
            except Exception as exc:
                log.warning("canli karar kurulamadi: %s", exc)

        log.info("hazir: %d madde", store.sayi())
    return _kaynaklar


# Yerel kulliyattan bu sayidan az karar gelirse Yargitay'a canli cikilir.
# 1 degil 2: tek bir karar cogu zaman konuya teget bir kararla eslesmis
# oluyor ve avukata "emsal yok" demekten farksiz.
CANLI_YEDEK_SINIRI = 2

# ILK cevapta gosterilecek karar sayisi. Uc yeterli DEGIL ama dogru
# cozum daha cok karar cekmek degil, ISTEGE BAGLI cekmek: panelde
# "Daha fazla karar getir" dugmesi var ve ona basilinca 12 karar daha
# geliyor.
#
# NEDEN: canli cekim her soruya 10-30 saniye ekliyordu ve Cloudflare
# tunelinin origin zaman asimi 100 saniye -- asilinca istek "524" ile
# tumden dusuyor, avukat cevabin TAMAMINI kaybediyor. Olculdu, site
# 90 saniye-2 dakikaya cikmisti.
KARAR_ADEDI = int(os.getenv("KARAR_ADEDI", "3"))

# Yeniden siralayici puani bunun altindaysa gelen kararlar konuyla
# yalnizca tesaduf eseri ortusuyor demektir. OLCULDU (ayni kulliyat,
# ayni soru, tek fark sorgunun bicimi):
#
#   soru "babam olmeden once tapuyu kardesime devretmis, mirastan
#         pay alabilir miyim"                -> 0,495 / 0,495 / 0,492
#                                               (3. HD, 3. HD, 21. HD -- yanlis)
#   terim "muris muvazaasi"                  -> 0,810 / 0,810
#                                               (Hukuk Genel Kurulu -- dogru)
#
# Dogru kararlar KULLIYATTA ZATEN VARDI; ham cumleyle sorulduklari icin
# bulunamiyorlardi. Iyi eslesmeler olculdugunde 0,81-0,90 bandinda
# cikiyor, kotu eslesme 0,49. Esik ikisinin arasina konuldu.
KARAR_SKOR_ESIGI = float(os.getenv("KARAR_SKOR_ESIGI", "0.65"))


def _en_iyi_skor(kararlar: list[dict]) -> float:
    """Iki havuzu kiyaslamak icin HAM cross-encoder puani.

    Normalize edilmis "skor" alani bu is icin kullanilamaz; sebebi
    _ce()'nin aciklamasinda. (_ce asagida tanimli; modul duzeyinde
    oldugu icin cagri aninda ikisi de hazir.)
    """
    return _ce(kararlar)


def _canli_once(k: dict, soru: str, guven_dusuk: bool) -> tuple[list[dict], str]:
    """CANLI ana katman: once Yargitay'a cikilir, yerel yedektir.

    NEDEN BOYLE
    Onceden indirilen kulliyat elle yazilmis 55 anahtarlik bir listeyle
    sinirliydi ve o listeyi bir insan yazdi, veriden cikarmadi. Nadir
    konu sorulunca karar bolumu bos geliyordu -- Yargitay'da o konuda
    yuz binlerce karar dururken. Canli katman bu siniri kaldiriyor:
    kapsam artik indirdigimiz kadar degil, Yargitay'in tamami.

    YEDEK NEDEN DURUYOR
    Canli katman tek noktaya bagimli. Bunun teorik olmadigi olculdu:
      - Yargitay 429 (Too Many Requests) donuyor; tek istemcili bir
        cekimde 1.253 belge (%17) bu yuzden dustu
      - Danistay tarafinda ayni risk GERCEKLESTI: captcha cikti, cekim
        40 kararda durdu ve o alan hala bos
    Yerel kulliyat olmasa boyle bir anda karar bolumu tumden olurdu.
    Simdi yalnizca zayifliyor.

    Doner: (kararlar, kaynak)
    """
    canli = k.get("canli_karar")
    if guven_dusuk or canli is None:      # soru kulliyatla ilgisiz
        return [], "yerel"
    try:
        ek = canli.ara(soru, limit=KARAR_ADEDI)
    except Exception as exc:              # ag hatasi cevabi engellememeli
        log.warning("canli karar cekimi basarisiz: %s", str(exc)[:120])
        return [], "yerel"
    return ek, "canli"


def _ce(kararlar: list[dict]) -> float:
    """En iyi HAM cross-encoder puani.

    "skor" alani KULLANILAMAZ: yeniden siralayici onu havuz icinde
    min-max normalize ediyor, yani birinci sira her zaman 1,0 aliyor.
    Canli kararlarda RRF puani olmadigi icin sonuc daima 0,95 x 0,90 =
    0,855 cikiyordu -- kalitesinden bagimsiz bir sabit. Iki farkli
    havuzu kiyaslamanin tek dogru yolu ham cross-encoder puani.
    """
    return max((k.get("ce_skor", -1.0) for k in kararlar), default=-1.0)


def _en_iyi_kararlar(k: dict, soru: str,
                     guven_dusuk: bool) -> tuple[list[dict], str]:
    """Canli ANA katman; yerel arsiv de bakilir, iyi olan gosterilir.

    NEDEN IKISI DE
    Canli katman kapsami acti: artik indirdigimiz kadariyla sinirli
    degiliz. Ama olculdu -- ustunluk soruya gore degisiyor (6 soru, ham
    cross-encoder puani):

        soru                       yerel  yerel+terim  canli
        kidem tazminati            0,949      0,983    0,738
        iki hakli ihtar tahliye    0,999      0,999    0,999
        muris muvazaasi            0,001      0,616    0,088
        marka hukumsuzlugu         0,103      0,356    0,949
        patent tecavuzu            0,005      0,016    0,948
        cekte zamanasimi           0,782      0,457    0,988
        ---------------------------------------------------
        kazanan                    1          2        3

    Indirilmis alanlarda (is, kira) yerel daha iyi; hic indirilmemis
    alanlarda (marka, patent) yerel fiilen sifir. Yani biri digerinin
    yerine gecmiyor.

    Yerel aramanin sorgu anindaki maliyeti sifira yakin (~0,3 sn, ag
    yok, Gemini yok) ve canli zaten yapiliyor. Ikisini de bakip iyisini
    secmek, canliyi tek basina kullanmaya gore hicbir sey kaybettirmez.
    """
    if guven_dusuk:                       # soru kulliyatla ilgisiz
        return [], "yerel"

    # YEREL ONCE. Yerel arama ag istegi yapmiyor ve saniyenin altinda
    # bitiyor; canli cekim 10-30 saniye ekliyor. Her soruda aga cikmak
    # cevabi 90 saniye-2 dakikaya cikariyordu ve Cloudflare tuneli
    # 100 saniyede "524" ile istegi kesiyordu.
    yerel_sonuc: list[dict] = []
    if k.get("karar") is not None:
        try:
            yerel_sonuc = k["karar"].ara(soru, limit=KARAR_ADEDI)
        except Exception as exc:          # yerel taraf cevabi engellememeli
            log.warning("yerel karar aramasi basarisiz: %s", str(exc)[:80])

    # Canliya yalnizca yerel ZAYIF kaldiginda cikiyoruz. Kapsam yine
    # sinirsiz: kullanici "Daha fazla karar getir" dugmesiyle her zaman
    # canliya erisebiliyor (/api/kararlar), ama bunun bedelini yalnizca
    # isteyen odemis oluyor.
    canli_sonuc: list[dict] = []
    if len(yerel_sonuc) < CANLI_YEDEK_SINIRI:
        canli_sonuc, _ = _canli_once(k, soru, guven_dusuk)

    return _kararlari_birlestir(yerel_sonuc, canli_sonuc)


def _karar_tarihi(k: dict) -> tuple:
    """gg.aa.yyyy -> siralanabilir demet. Tarih yoksa en eskiye koyar."""
    parcalar = (k.get("karar_tarihi") or "").split(".")
    if len(parcalar) != 3:
        return (0, 0, 0)
    try:
        g, a, y = (int(x) for x in parcalar)
        return (y, a, g)
    except ValueError:
        return (0, 0, 0)


def _kararlari_birlestir(yerel: list[dict], canli: list[dict],
                         limit: int = KARAR_ADEDI) -> tuple[list[dict], str]:
    """Iki havuzu BIRLESTIRIR; birini secmez.

    ONCE BIRINI SECIYORDU ve bu yanlisti. Iki havuz en yuksek ce_skor'a
    gore kiyaslaniyordu; olculdu, puanlar DOYUYOR:

        "kiraci iki hakli ihtar nedeniyle tahliye edilebilir mi"
        yerel  8 kararin 8'i de ce = 0,999
        canli  8 kararin 6'si  ce = 0,999

    Tavana vurmus iki sayiyi karsilastirmak yazi-tura demek. Ustelik
    secim yapmak bilgi ATIYOR: kaybeden havuzdaki kararlar da alakali.

    TARIH IKINCIL OLCUT. Alaka esitken YENI karar daha degerli: mevzuat
    ve ictihat degisiyor. Kullanicinin sikayeti tam buydu -- "bula bula
    2009 mu bulmus". (O ornekte eskilik kismen dogruydu: kira davalarina
    bakan 6. Hukuk Dairesi 2016'da kapandi, gorevi 3. HD'ye gecti. Yine
    de yeniyi one almak dogru sira.)
    """
    gorulen: set[str] = set()
    hepsi: list[dict] = []
    for k in list(yerel) + list(canli):
        kimlik = (k.get("kisa_ad") or "").strip() or                  f"{k.get('esas_no', '')}|{k.get('karar_no', '')}"
        if kimlik in gorulen:
            continue
        gorulen.add(kimlik)
        hepsi.append(k)

    hepsi.sort(key=lambda k: (round(k.get("ce_skor", 0.0), 3), _karar_tarihi(k)),
               reverse=True)
    kirpik = hepsi[:limit]
    if not kirpik:
        return [], "yerel"
    canli_var = any(k.get("canli") for k in kirpik)
    yerel_var = any(not k.get("canli") for k in kirpik)
    kaynak = "karma" if (canli_var and yerel_var) else ("canli" if canli_var else "yerel")
    return kirpik, kaynak


def _kararlari_iyilestir(k: dict, soru: str, kararlar: list[dict],
                         guven_dusuk: bool) -> tuple[list[dict], str]:
    """Karar sonuclari zayifsa once YERELDE, sonra CANLI olarak duzeltir.

    Uc kademeli merdiven. Sirasi onemli, cunku her kademe bir oncekinden
    pahali:

      1. ham soru + yerel indeks      0 ek maliyet
      2. hukuki terim + yerel indeks  ~0,6 sn (bir Gemini cagrisi)
      3. hukuki terim + canli Yargitay ~11 sn (ag)

    Cogu soru 1. kademede bitiyor; merdiven yalnizca sonuc zayifken
    tirmaniyor. Terime cevirme adimi kanun tarafinda (HyDE) zaten vardi,
    karar tarafinda YOKTU -- asil hata buydu.

    Doner: (kararlar, kaynak) -- kaynak arayuzde gosteriliyor.
    """
    if guven_dusuk:                   # soru kulliyatla ilgisiz
        return kararlar, "yerel"

    if _en_iyi_skor(kararlar) >= KARAR_SKOR_ESIGI:
        return kararlar, "yerel"

    canli = k.get("canli_karar")
    if canli is None:
        return kararlar, "yerel"

    from core.canli_karar import arama_terimi
    try:
        terim = arama_terimi(soru, k["generator"])
    except Exception as exc:
        log.warning("arama terimi uretilemedi: %s", str(exc)[:80])
        return kararlar, "yerel"
    if not terim:
        return kararlar, "yerel"

    # 2. kademe: AYNI kulliyat, duzgun sorgu. Ag istegi yok.
    if k.get("karar") is not None:
        try:
            terimle = k["karar"].ara(terim, limit=KARAR_ADEDI)
            if _en_iyi_skor(terimle) > _en_iyi_skor(kararlar):
                kararlar = terimle
        except Exception as exc:
            log.warning("terimle karar aramasi basarisiz: %s", str(exc)[:80])

    if _en_iyi_skor(kararlar) >= KARAR_SKOR_ESIGI:
        return kararlar, "yerel-terim"

    # 3. kademe: kulliyatta gercekten yok; Yargitay'dan canli cek.
    try:
        ek = canli.ara(soru, limit=KARAR_ADEDI)
    except Exception as exc:          # ag hatasi cevabi engellememeli
        log.warning("canli karar cekimi basarisiz: %s", str(exc)[:120])
        return kararlar, "yerel-terim"

    if _en_iyi_skor(ek) > _en_iyi_skor(kararlar):
        return ek, "canli"
    return kararlar, "yerel-terim"


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


# ---------------------------------------------------------------- belge
# BELGE YUKLEME. Iki adimli, cunku tek adimli olamaz: avukat neyin
# disari gittigini GORMEDEN gondermemeli.
#
#   1) /api/belge        dosya -> yerelde metin -> maskele -> ONAYA sun
#   2) /api/belge/analiz onaylanan maskeli metin -> mesele -> arama
#
# Ham dilekce hicbir zaman disari cikmiyor; Gemini yalnizca ikinci
# adimda ve yalnizca maskelenmis metni goruyor. Esleme tablosu bu
# surecin BELLEGINDE, kullanicinin kendi makinesinde duruyor -- diske
# yazilmiyor, cevaba konmuyor.
_MASKELER: dict[str, tuple[float, object]] = {}
BELGE_OMRU = 3600.0          # bir saat sonra bellekten dusuyor
EN_BUYUK_BELGE = 10 * 1024 * 1024


def _maske_temizle() -> None:
    simdi = time.time()
    for anahtar in [k for k, (t, _) in _MASKELER.items()
                    if simdi - t > BELGE_OMRU]:
        _MASKELER.pop(anahtar, None)


@app.post("/api/belge")
async def belge_yukle(dosya: UploadFile = File(...)):
    """Belgeyi YERELDE metne cevirir, maskeler ve onaya sunar.

    Bu uc Gemini'yi hic cagirmiyor. Donen sey kullanicinin gorecegi
    maskelenmis metin ve maskelenmesi onerilen adaylar.
    """
    from core.belge import adaylar as aday_bul
    from core.belge import metne_cevir
    from core.maskele import Maske

    veri = await dosya.read()
    if len(veri) > EN_BUYUK_BELGE:
        raise HTTPException(413, "Dosya 10 MB'tan buyuk.")
    try:
        metin = metne_cevir(veri, dosya.filename or "")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not metin.strip():
        raise HTTPException(422, "Belgeden metin cikarilamadi. "
                                 "Taranmis (goruntu) PDF olabilir.")

    maske = Maske()
    onerilen = aday_bul(metin)
    for tur, liste in onerilen.items():
        for deger in liste:
            maske.ekle(deger, tur)
    maskeli = maske.maskele_degerler(maske.maskele(metin))

    _maske_temizle()
    oturum = secrets.token_urlsafe(16)
    _MASKELER[oturum] = (time.time(), maske)

    # ADAY DEGERLERI CEVABA KONMUYOR. Tarayici cogu zaman ayni
    # makinede ama tunelden baglanildiginda cevap internete cikiyor;
    # o durumda isim ve adresler de cikardi. Kullanicinin gormesi
    # gereken sey zaten maskelenmis metin: bir sey gozden kacmissa
    # metinde durur ve elle duzeltir. Boylece tanimlayici degerler
    # HICBIR kosulda bu surecin disina cikmiyor.
    return {
        "oturum": oturum,
        "maskeli": maskeli,
        "ozet": maske.ozet(),
        "karakter": len(metin),
    }


class BelgeAnaliz(BaseModel):
    oturum: str
    maskeli: str                      # kullanicinin duzenledigi hali
    ek_gizli: list[str] = []          # elle isaretledigi ek degerler


@app.post("/api/belge/analiz")
def belge_analiz(istek: BelgeAnaliz):
    """Onaylanmis MASKELI metinden meseleleri cikarip her birini arar."""
    kayit = _MASKELER.get(istek.oturum)
    if not kayit:
        raise HTTPException(404, "Oturum bulunamadi ya da zaman asimina ugradi. "
                                 "Belgeyi yeniden yukleyin.")
    maske = kayit[1]
    metin = istek.maskeli
    for deger in istek.ek_gizli:
        if deger.strip():
            maske.ekle(deger.strip(), "KISI")
    metin = maske.maskele_degerler(metin)

    k = kaynaklar()
    from core.mesele import meseleleri_ayir

    meseleler = meseleleri_ayir(metin, k["generator"]) or []
    if not meseleler:
        raise HTTPException(422, "Belgeden ayri hukuki mesele cikarilamadi.")

    bolumler = []
    for mesele in meseleler:
        maddeler = k["retriever"].ara(mesele, limit=5)
        bolumler.append({
            "mesele": mesele,
            "maddeler": [{
                "mevzuat_adi": m.get("mevzuat_adi"),
                "mevzuat_no": m.get("mevzuat_no"),
                "madde_no": m.get("madde_no"),
                "baslik": m.get("baslik"),
                "metin": (m.get("metin") or "")[:1200],
                "mulga": m.get("mulga"),
            } for m in maddeler],
        })
    return {"bolumler": bolumler, "mesele_sayisi": len(meseleler),
            "ozet": maske.ozet()}


# ---------------------------------------------------------------- arsiv
# BURONUN KENDI BELGELERINDE ARAMA. Mevzuat aramasindan iki farki var:
# birim BELGE (parca degil) ve BULUT CAGRISI YOK -- sorgu yerelde
# gomuye cevrilip yerel indekste araniyor. Internetsiz calisir.
_ARSIV = {}


def _arsiv():
    from core.arsiv import Arsiv

    if "a" not in _ARSIV:
        k = kaynaklar()
        a = Arsiv(k["retriever"].embedder)
        if not (a.dizin / "vektorler.npy").exists():
            raise HTTPException(404, "Arsiv indeksi bulunamadi.")
        a.yukle()
        _ARSIV["a"] = a
    return _ARSIV["a"]


@app.get("/api/arsiv/durum")
def arsiv_durum():
    from core.arsiv import Arsiv

    a = Arsiv(None)
    if not (a.dizin / "parcalar.json").exists():
        return {"hazir": False, "belge": 0, "parca": 0}
    parcalar = json.loads((a.dizin / "parcalar.json").read_text("utf-8"))
    return {"hazir": True, "parca": len(parcalar),
            "belge": len({p["belge"] for p in parcalar})}


class ArsivSorgu(BaseModel):
    soru: str
    adet: int = 6


@app.post("/api/arsiv/ara")
def arsiv_ara(istek: ArsivSorgu):
    soru = (istek.soru or "").strip()
    if not soru:
        raise HTTPException(422, "Bos sorgu.")
    sonuclar = _arsiv().ara(soru, limit=max(1, min(istek.adet, 20)))
    return {"soru": soru, "sonuclar": sonuclar}


class MaskeliPdf(BaseModel):
    metin: str
    ad: str = "maskeli-belge"


@app.post("/api/belge/pdf")
def maskeli_pdf(istek: MaskeliPdf):
    """Maskeli metni PDF olarak doner.

    NEDEN: avukat maskelenmis surumu kendi elinde tutmak isteyebilir.
    Baska bir araca (kendi ChatGPT'sine, meslektasina) verecekse ham
    dilekceyi degil bunu vermeli. Uretim tamamen yerelde; bu uc de
    Gemini'yi cagirmiyor.
    """
    from fastapi.responses import Response

    from core.belge import pdfe_dok

    metin = (istek.metin or "").strip()
    if not metin:
        raise HTTPException(422, "Bos metin PDF'e cevrilemez.")
    if len(metin) > 400_000:
        raise HTTPException(413, "Metin cok uzun.")
    try:
        veri = pdfe_dok(metin)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))

    # Ad dogrudan Content-Disposition basligina giriyor. Dosya yazmadigimiz
    # icin yol asimi degil, ama arka arkaya nokta ("..") indirme adinda
    # tarayiciya gore garip davraniyor; nokta dizileri tekile indiriliyor.
    guvenli = re.sub(r"[^A-Za-z0-9._-]+", "-", istek.ad or "")
    guvenli = re.sub(r"\.{2,}", ".", guvenli).strip(".-")[:60]
    return Response(
        content=veri, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="{guvenli or "maskeli-belge"}.pdf"'})


class DahaKarar(BaseModel):
    soru: str
    adet: int = 12
    haric: list[str] = []          # zaten gosterilenler


@app.post("/api/kararlar")
def daha_karar(istek: DahaKarar):
    """Ayni soru icin DAHA COK karar getirir.

    NEDEN AYRI UC
    Cevap uretimi pahali (Gemini + vurgu + karsi taraf); yalnizca daha
    cok emsal gormek icin butun akisi tekrar calistirmak gereksiz.
    Burada yalnizca karar arama yapiliyor.

    Varsayilan gosterim alti karar. Avukat emsal ararken bu az kalabilir
    -- ozellikle hepsi ayni daireden ve yakin tarihliyse -- ama her
    soruda otuz karar cekmek hem yavas hem Yargitay'a yuk. Bu yuzden
    "daha fazla" istege bagli.
    """
    k = kaynaklar()
    n = max(1, min(int(istek.adet or 12), 30))
    haric = {x for x in (istek.haric or []) if x}

    yerel: list[dict] = []
    if k.get("karar") is not None:
        try:
            yerel = k["karar"].ara(istek.soru, limit=n)
        except Exception as exc:
            log.warning("yerel karar aramasi basarisiz: %s", str(exc)[:80])

    canli: list[dict] = []
    if k.get("canli_karar") is not None:
        try:
            canli = k["canli_karar"].ara(istek.soru, limit=n)
        except Exception as exc:      # ag hatasi bos liste dondursun
            log.warning("canli karar cekimi basarisiz: %s", str(exc)[:120])

    kararlar, kaynak = _kararlari_birlestir(yerel, canli, limit=n + len(haric))
    kararlar = [x for x in kararlar
                if (x.get("kisa_ad") or "") not in haric][:n]
    return {
        "kaynak": kaynak,
        "kararlar": [{
            "kisa_ad": kr.get("kisa_ad", ""),
            "daire": kr.get("daire", ""),
            "esas_no": kr.get("esas_no", ""),
            "karar_no": kr.get("karar_no", ""),
            "karar_tarihi": kr.get("karar_tarihi", ""),
            "metin": kr.get("gerekce") or kr.get("metin", ""),
            "skor": round(kr.get("skor", 0), 4),
            "ce_skor": round(kr.get("ce_skor", 0), 4),
            "canli": bool(kr.get("canli")),
        } for kr in kararlar],
    }


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


# Iliski turlerinin kullaniciya gosterilecek adi. Ham etiket ("gonderme")
# hukukcuya bir sey anlatmiyor.
ILISKI_ADI = {
    "istisna": "istisnası",
    "yaptirim": "yaptırımı",
    "gonderme": "gönderme yapıyor",
    "degistirir": "değiştiriyor",
    "mulga": "yürürlükten kaldırıyor",
    "atif": "atıf yapıyor",
}


def graf_baglantilari(m: dict, kaynak: dict) -> dict:
    """Maddenin yaptigi ve aldigi atiflar, okunabilir adlarla.

    Kanit cumlesi kanunun KENDI metninden birebir aliniyor; uretilmis
    ozet degil, yani uydurma riski yok.
    """
    g = kaynak.get("graf")
    if g is None:
        return {"yapilan": [], "alinan": []}
    adlar = kaynak.get("madde_adlari", {})
    no, madde_no = m.get("mevzuat_no", ""), str(m.get("madde_no", ""))

    def coz(anahtar):
        kanun, _, mad = anahtar.partition("-")
        ad, baslik = adlar.get(anahtar, ("", ""))
        return {"anahtar": anahtar, "mevzuat_no": kanun, "madde_no": mad,
                "mevzuat_adi": ad, "baslik": baslik,
                "kulliyatta": anahtar in adlar}

    # AYNI HEDEF BIR KEZ. Metinde ayni maddeye birden fazla atif olabiliyor
    # ve her biri ayri iliski turu aliyor; ekranda "m.17 gonderme yapiyor"
    # ve "m.17 atif yapiyor" alt alta gorununce avukat icin gurultu oluyor.
    # Daha BELIRLEYICI iliski kazaniyor: "istisnasidir" bilgisi
    # "atif yapiyor"dan cok daha degerli.
    oncelik = {"mulga": 0, "degistirir": 1, "istisna": 2, "yaptirim": 3,
               "gonderme": 4, "atif": 5}
    en_iyi: dict[str, dict] = {}
    for e in g.atiflar(no, madde_no):
        h = e["hedef"]
        onceki = en_iyi.get(h)
        if onceki is None or oncelik.get(e["iliski"], 9) < onceki["_p"]:
            en_iyi[h] = {**e, "_p": oncelik.get(e["iliski"], 9)}

    yapilan = []
    for e in list(en_iyi.values())[:12]:
        d = coz(e["hedef"])
        d["iliski"] = ILISKI_ADI.get(e["iliski"], e["iliski"])
        d["kanit"] = e.get("kanit", "")
        yapilan.append(d)
    alinan = [coz(a) for a in g.atif_yapanlar(no, madde_no)[:12]]
    return {"yapilan": yapilan, "alinan": alinan}


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


def metrik_yaz(soru: str, bas: float, maddeler: list, vektor_puani: float,
               guven_dusuk: bool, karar_sayisi: int, cevap_var: bool) -> None:
    """Sorgu suresini ve isabet isaretlerini bir satir olarak yazar.

    NEDEN VAR
    Hangi sorgularin yavas ya da zayif oldugunu ancak gercek kullanimda
    gorebiliyoruz. Sure ve guven puani kayitli olmazsa "avukat sikayet
    etti" disinda bir isaret kalmiyor.

    VARSAYILAN KAPALI. Kayit SORU METNINI de tutuyor; site disariya
    aciksa baskalarinin sorgulari da yazilir ve bu, sahibinin bilerek
    vermesi gereken bir karar. METRIK=1 ile acilir.
    """
    if not config.METRIK:
        return
    try:
        ilk = maddeler[0] if maddeler else {}
        satir = {
            "an": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sure": round(time.time() - bas, 2),
            "soru": soru[:300],
            "madde": len(maddeler),
            "ilk": f"{ilk.get('mevzuat_no', '')} m.{ilk.get('madde_no', '')}",
            "guven": round(vektor_puani, 3),
            "guven_dusuk": guven_dusuk,
            "karar": karar_sayisi,
            "cevap": cevap_var,
        }
        config.METRIK_YOLU.parent.mkdir(parents=True, exist_ok=True)
        with config.METRIK_YOLU.open("a", encoding="utf-8") as f:
            f.write(json.dumps(satir, ensure_ascii=False) + "\n")
    except Exception as exc:      # olcum, cevabi asla engellememeli
        log.debug("metrik yazilamadi: %s", exc)


@app.post("/api/sor")
def sor(istek: Soru):
    if not istek.soru.strip():
        return JSONResponse({"hata": "Soru bos"}, status_code=400)

    bas = time.time()
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

    kararlar, karar_kaynagi = [], "yerel"
    if config.CANLI_ONCE:
        kararlar, karar_kaynagi = _en_iyi_kararlar(k, istek.soru, guven_dusuk)
    else:
        if k.get("karar") is not None:
            try:
                kararlar = k["karar"].ara(istek.soru, limit=KARAR_ADEDI)
            except Exception as exc:  # karar tarafi cevabi engellememeli
                log.warning("karar aramasi basarisiz: %s", exc)
        kararlar, karar_kaynagi = _kararlari_iyilestir(
            k, istek.soru, kararlar, guven_dusuk)

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

    metrik_yaz(istek.soru, bas, maddeler, vektor_puani, guven_dusuk,
               len(kararlar), bool(cevap))

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
            "graf": graf_baglantilari(m, k),
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
            # Yerel kararlarda ayristirilmis "gerekce", canli cekilende
            # ham "metin" var. Yalnizca gerekce'ye bakmak canli kararin
            # govdesini BOS gosteriyordu.
            "metin": kr.get("gerekce") or kr.get("metin", ""),
            "skor": round(kr.get("skor", 0), 4),
            # Havuzdan bagimsiz mutlak alaka puani; iki kaynagi
            # kiyaslamanin tek gecerli olcusu.
            "ce_skor": round(kr.get("ce_skor", 0), 4),
            "canli": bool(kr.get("canli")),
        } for kr in kararlar],
        # Kararlarin nereden geldigi: "yerel" | "yerel-terim" | "canli".
        # Avukat kaynagi bilmeli; canli kararlar henuz indekse girmemis
        # olabilir ve bir daha ayni siralamada gelmeyebilir.
        "karar_kaynagi": karar_kaynagi,
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
