"""mevzuat-rag komut satiri.

Tipik akis:
    python cli.py katalog              # mevzuat listesini cek
    python cli.py cek --pilot          # metinleri indir + madde JSON'a cevir
    python cli.py indeksle             # GPU'da embed et, Qdrant + BM25 kur
    python cli.py sor "yillik izin kac gun"
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("cli")

# Pilot icin temel kanunlar: (no, tur, tertip)
PILOT = [
    ("4857", 1, "5"),   # Is Kanunu
    ("6098", 1, "5"),   # Turk Borclar Kanunu
    ("4721", 1, "5"),   # Turk Medeni Kanunu
    ("5237", 1, "5"),   # Turk Ceza Kanunu
    ("6100", 1, "5"),   # Hukuk Muhakemeleri Kanunu
    ("6698", 1, "5"),   # Kisisel Verilerin Korunmasi Kanunu
]

def guvenli_yaz(yol, veri) -> None:
    """Once gecici dosyaya yazip sonra yer degistirir.

    Dogrudan uzerine yazmak tehlikeli: 358 MB'lik kulliyat dosyasi
    yazilirken surec olurse ya da iki surec ayni anda yazarsa dosya
    sifirlaniyor. Bir kez yasandi -- maddeler.json 0 bayta dustu ve
    275.806 madde ancak yedekten geri getirilebildi.

    os.replace ayni dizin icinde atomik: ya eski dosya ya yeni dosya
    gorunur, arada bos hal olmaz.

    Yazim AKITILARAK yapiliyor: json.dumps once tum dosyayi tek parca
    dizgi olarak bellekte kuruyor. 271 bin maddede bu ~800 MB ek bellek
    demek ve cekim isi tam bu satirda MemoryError ile coktu (11.999.
    belgede). json.dump ayni ciktiyi dogrudan dosyaya yaziyor.
    """
    import os
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    with gecici.open("w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


KATALOG_YOLU = config.RAW_DIR / "katalog.json"
MADDE_YOLU = config.RAW_DIR / "maddeler.json"


def cmd_katalog(args) -> None:
    from scraper.client import MevzuatClient
    from scraper import catalog

    c = MevzuatClient()
    # Onceki katalogu koru. Komut tek bir turu cekmek icin calistirildiginda
    # dosyayi bastan yaziyor ve diger turlerin listesini siliyordu.
    onceki: dict[tuple, object] = {}
    if not args.sifirdan and KATALOG_YOLU.exists():
        for k in catalog.yukle(KATALOG_YOLU):
            onceki[(k.tur, k.mevzuat_no, k.tertip)] = k
        log.info("mevcut katalogda %d kayit korunuyor", len(onceki))

    for tur in args.tur:
        kayitlar = catalog.listele(c, tur=tur, limit=args.limit)
        log.info("tur %d (%s): %d kayit", tur, config.MEVZUAT_TURLERI.get(tur, "?"), len(kayitlar))
        for k in kayitlar:
            onceki[(k.tur, k.mevzuat_no, k.tertip)] = k
        catalog.kaydet(list(onceki.values()), KATALOG_YOLU)   # tur bitince yaz

    log.info("toplam %d kayit -> %s", len(onceki), KATALOG_YOLU)


def cmd_cek(args) -> None:
    from scraper.client import MevzuatClient
    from scraper.parser import parse_pdf, parse_html

    c = MevzuatClient()

    if args.pilot:
        hedefler = [(no, tur, tertip, "", "", False) for no, tur, tertip in PILOT]
    else:
        if not KATALOG_YOLU.exists():
            sys.exit("Once 'python cli.py katalog' calistirin.")
        from scraper import catalog
        kayitlar = catalog.yukle(KATALOG_YOLU)
        if args.limit:
            kayitlar = kayitlar[:args.limit]
        hedefler = [(k.mevzuat_no, k.tur, k.tertip, k.ad, k.pdf_url, k.metinsiz)
                    for k in kayitlar]

    # Katalog sirasi belirli oldugu icin yarim kalan bir calisma buradan
    # devam ettirilebilir. --yenile-tur ile calisirken hicbir belge
    # atlanmiyor; ara kayda kadar islenmis binlerce belgeyi bastan
    # ayristirmak saatler yiyor.
    if args.baslangic:
        atlanan = min(args.baslangic, len(hedefler))
        log.info("ilk %d belge atlaniyor (--baslangic)", atlanan)
        hedefler = hedefler[atlanan:]

    # Mevcut veriyi koru: cek komutu daha once dosyayi bastan yaziyordu ve
    # eksikleri tamamlamak icin calistirildiginda onceki her seyi siliyordu.
    mevcut: dict[str, dict] = {}
    if not args.sifirdan and MADDE_YOLU.exists():
        for m in json.loads(MADDE_YOLU.read_text(encoding="utf-8")):
            mevcut[m["chunk_id"]] = m
        log.info("mevcut %d madde korunuyor", len(mevcut))

    # Bu calismada yeniden ayristirilan belgeler. Eski kayitlari atilmali:
    # ayristirici duzelince madde numaralari degisebiliyor ("3 (2)" -> "3/A")
    # ve yalnizca chunk_id uzerinden birlestirirsek eski HATALI kayit da
    # kulliyatta kaliyor; ayni hukum iki kez, biri bozuk halde gorunuyor.
    yenilenen: set[tuple] = set()

    def kaydet(yeniler: list[dict]) -> None:
        birlesik = {cid: m for cid, m in mevcut.items()
                    if (m["mevzuat_no"], m["tertip"], m["mevzuat_tur"])
                    not in yenilenen}
        for m in yeniler:
            birlesik[m["chunk_id"]] = m
        guvenli_yaz(MADDE_YOLU, list(birlesik.values()))

    # Zaten indirilmis belgeleri atla. --yenile-tur ile verilen turler
    # atlanmaz: PDF adresi ya da ayristirici duzeldiginde o turleri yeniden
    # cekmek gerekiyor (eski kayitlar HTML'den gelmis olabilir; HTML uzun
    # belgeleri sessizce kesiyor).
    yenilenecek = set(args.yenile_tur or ())
    islenmis = {(m["mevzuat_no"], m["tertip"], m["mevzuat_tur"])
                for m in mevcut.values()}

    tum_maddeler, basarisiz = [], []
    for i, (no, tur, tertip, ad, pdf_url, metinsiz) in enumerate(hedefler, 1):
        # Sadece sonda kaydedersek 900. belgede olusan bir hata butun isi cope
        # atar; arada diske yaziyoruz. Aralik 400: dosya 375 MB ve her yazim
        # tam yeniden yazim demek -- 50'de bir yazarken tur suzgecli bir
        # calisma 80 GB'lik gereksiz disk yazimi cikariyordu.
        # Yalnizca yeni madde varken yaz. Tur suzgeciyle calisirken (or.
        # --yenile-tur 1) dongu 14.439 belgenin cogunu atliyor; kosulsuz
        # yazarsak her 50 atlamada 375 MB'lik dosya bosuna yeniden yaziliyor.
        if i % 400 == 0 and tum_maddeler:
            kaydet(tum_maddeler)
            log.info("--- ara kayit: %d kanun islendi, %d madde ---",
                     i, len(tum_maddeler))

        tur_adi = config.MEVZUAT_TURLERI.get(tur, "Mevzuat")
        if (not args.sifirdan and tur not in yenilenecek
                and (no, tertip, tur_adi) in islenmis):
            continue                      # bu belge zaten var
        try:
            # PDF birincil kaynak: iframe HTML uzun kanunlari kesiyor.
            if metinsiz:      # taranmis goruntu; metin katmani yok
                basarisiz.append((no, "metin katmani yok"))
                continue
            maddeler = parse_pdf(c.mevzuat_pdf(tur, no, tertip, pdf_url=pdf_url),
                                 tur_adi=tur_adi, mevzuat_no=no, tertip=tertip)
            kaynak = "pdf"
            if not maddeler:
                maddeler = parse_html(c.mevzuat_html(tur, no, tertip),
                                      tur_adi=tur_adi, mevzuat_no=no, tertip=tertip)
                kaynak = "html"
            if not maddeler:
                basarisiz.append((no, "madde bulunamadi"))
                if len(basarisiz) % 50 == 0:
                    log.warning("madde uretmeyen belge sayisi: %d", len(basarisiz))
                continue
            yenilenen.add((no, tertip, tur_adi))
            tum_maddeler.extend(m.to_dict() for m in maddeler)
            log.info("[%d/%d] %s (%s): %d madde [%s]", i, len(hedefler), no,
                     maddeler[0].mevzuat_adi[:40], len(maddeler), kaynak)
        except Exception as exc:
            basarisiz.append((no, str(exc)[:80]))
            log.warning("[%d/%d] %s BASARISIZ: %s", i, len(hedefler), no, exc)

    kaydet(tum_maddeler)
    log.info("toplam %d madde -> %s", len(tum_maddeler), MADDE_YOLU)
    if basarisiz:
        log.warning("%d mevzuat alinamadi (ilk 5): %s", len(basarisiz), basarisiz[:5])
        (config.RAW_DIR / "basarisiz.json").write_text(
            json.dumps(basarisiz, ensure_ascii=False, indent=1), encoding="utf-8")


# Baslangicta yalnizca is hukuku vardi (Is Kanunu zaten indekste oldugu
# icin "kanun + karar" birlesimini gosterebilecegimiz tek alan oydu).
# 01.09.2026'da alan cesitlendirildi: sistem yalnizca is hukuku sorularinda
# karar gosterebiliyordu, kira/bosanma/ceza sorularinda karar bolumu bos
# kaliyordu.
IS_HUKUKU_ANAHTARLARI = [
    "kıdem tazminatı",
    "ihbar tazminatı",
    "işe iade",
    "fazla mesai ücreti",
    "yıllık izin ücreti",
    "iş kazası tazminatı",
    "haklı nedenle fesih",
    "asgari ücret",
    "işçilik alacakları",
    "sendika özgürlüğü",
]

# Ikinci alan: kira hukuku. Once 17 alana yayilmak denendi ama alan basina
# ~150 karar dusuyordu ve bu, kullaniciya tutarsiz bir sistem gosteriyor --
# bir soruda karar cikiyor, benzerinde cikmiyor. Bunun yerine TEK bir alani
# duzgun kapsamak secildi.
#
# Kira secildi cunku: siradan insanin en sik karsilastigi ikinci konu, kurali
# Turk Borclar Kanunu'nda ve o maddeler zaten kulliyatta -- yani atif zinciri
# de calisiyor.
KIRA_ANAHTARLARI = [
    "kira bedelinin tespiti",
    "kira bedelinin artırılması",
    "tahliye taahhüdü",
    "ihtiyaç nedeniyle tahliye",
    "iki haklı ihtar",
    "kiralananın tahliyesi",
    "kira sözleşmesinin feshi",
    "kiracının temerrüdü",
    "depozito iadesi",
    "kiralananda ayıp",
    "alt kira ve kullanım hakkının devri",
    "kira sözleşmesinin devri",
]

KARAR_YOLU = config.RAW_DIR / "kararlar.json"


# Idari yargi anahtarlari. Kulliyatta yalnizca Yargitay karari vardi;
# memur, disiplin, atama, mobbing gibi uyusmazliklar idari yargiya gidiyor
# ve o kararlar Danistay'da. Olculdu: "kadrolu ogretmene mobbing" sorusunda
# sistem TBK m.417'yi getiriyordu, oysa o hukum ISCI icin.
IDARI_ANAHTARLAR = [
    "mobbing",
    "disiplin cezası",
    "kademe ilerlemesinin durdurulması",
    "görevden uzaklaştırma",
    "naklen atama",
    "atama iptali",
    "disiplin soruşturması",
    "aylıktan kesme cezası",
]

DANISTAY_YOLU = config.RAW_DIR / "danistay_kararlar.json"


def cmd_danistay(args) -> None:
    """Danistay kararlarini indirir.

    Captcha acilirsa DURUR: bot denetimini atlatmaya calismiyoruz.
    """
    from scraper.danistay import DanistayClient, CaptchaAcik

    # Istemci kurulurken de captcha cikabiliyor (acilis sayfasinda bayrak
    # aciksa). Kurulum try'in DISINDA kalirsa komut yigin iziyle cokuyor;
    # oysa bu bir hata degil, sunucunun "su an olmaz" demesi.
    try:
        istemci = DanistayClient(delay=args.gecikme)
    except CaptchaAcik as exc:
        log.error("DURDURULDU: %s", exc)
        log.error("Danistay su an captcha istiyor. Captcha cozulmuyor; "
                  "bir sure sonra yeniden deneyin.")
        return

    hepsi: dict[str, dict] = {}
    if DANISTAY_YOLU.exists():          # yarim kalmis indirmeyi surdur
        for k in json.loads(DANISTAY_YOLU.read_text(encoding="utf-8")):
            hepsi[k["id"]] = k
        log.info("%d Danistay karari zaten var", len(hepsi))

    def kaydet() -> None:
        guvenli_yaz(DANISTAY_YOLU, list(hepsi.values()))

    try:
        for kelime in args.anahtar:
            log.info("--- Danistay '%s' ---", kelime)
            kayitlar = istemci.ara(kelime, en_fazla=args.adet)
            log.info("'%s': %d kayit listelendi", kelime, len(kayitlar))
            for i, kayit in enumerate(kayitlar, 1):
                if kayit.id in hepsi:
                    continue
                kayit.metin = istemci.belge(kayit.id, kelime)
                if not kayit.metin:
                    continue
                hepsi[kayit.id] = kayit.to_dict()
                if i % 25 == 0:
                    kaydet()
                    log.info("  [%s] %d/%d (toplam %d)", kelime, i,
                             len(kayitlar), len(hepsi))
            kaydet()
    except CaptchaAcik as exc:
        kaydet()
        log.error("DURDURULDU: %s", exc)
        log.error("Captcha cozulmuyor. %d karar kaydedildi.", len(hepsi))
        return

    kaydet()
    log.info("toplam %d Danistay karari -> %s", len(hepsi), DANISTAY_YOLU)


def cmd_ictihat(args) -> None:
    from scraper.ictihat import EmsalClient

    istemci = EmsalClient(delay=args.gecikme)
    hepsi: dict[str, dict] = {}

    if KARAR_YOLU.exists():          # yarim kalmis indirmeyi surdur
        for k in json.loads(KARAR_YOLU.read_text(encoding="utf-8")):
            hepsi[k["id"]] = k
        log.info("%d karar zaten var, uzerine ekleniyor", len(hepsi))

    def kaydet() -> None:
        guvenli_yaz(KARAR_YOLU, list(hepsi.values()))

    anahtarlar = KIRA_ANAHTARLARI if args.kira else args.anahtar
    for kelime in anahtarlar:
        log.info("--- '%s' araniyor ---", kelime)
        kayitlar = istemci.ara(kelime, en_fazla=args.adet)
        log.info("'%s': %d kayit listelendi", kelime, len(kayitlar))

        for i, kayit in enumerate(kayitlar, 1):
            if kayit.id in hepsi:
                continue
            kayit.metin = istemci.belge(kayit.id)
            if not kayit.metin:
                continue
            hepsi[kayit.id] = kayit.to_dict()
            if i % 25 == 0:
                kaydet()
                log.info("  [%s] %d/%d indirildi (toplam %d)",
                         kelime, i, len(kayitlar), len(hepsi))

    kaydet()
    log.info("toplam %d benzersiz karar -> %s", len(hepsi), KARAR_YOLU)


def cmd_karar_indeksle(args) -> None:
    """Indirilmis kararlari AYRI bir vektor indeksine yazar.

    Mevzuat indeksine dokunmuyor: kararlar bozuk ya da eksik olsa bile kanun
    aramasi calismaya devam eder.
    """
    import numpy as np
    from core.embedder import Embedder
    from core.karar_ara import KARAR_INDEX_DIR
    from core.vektor import VektorDeposu
    from scraper.karar_parser import parse

    if not KARAR_YOLU.exists():
        sys.exit("Once 'python cli.py ictihat' calistirin.")
    ham = json.loads(KARAR_YOLU.read_text(encoding="utf-8"))
    log.info("%d Yargitay karari yuklendi", len(ham))

    # Danistay kararlari AYNI indekse giriyor: kullanici "hangi mahkeme"
    # diye dusunmuyor, meseleyi soruyor. Ayirt etmek gerektiginde kayitta
    # "mahkeme" alani var ve kisa_ad zaten "Danistay ..." diye basliyor.
    if DANISTAY_YOLU.exists():
        danistay = json.loads(DANISTAY_YOLU.read_text(encoding="utf-8"))
        log.info("%d Danistay karari yuklendi", len(danistay))
        ham = ham + danistay

    parcalar = [k for kayit in ham for k in parse(kayit)]
    if not parcalar:
        sys.exit("Kararlardan parca cikarilamadi.")
    log.info("%d karardan %d parca cikti (karar basina %.1f)",
             len(ham), len(parcalar), len(parcalar) / len(ham))

    emb = Embedder()
    vektorler = emb.encode_documents([k.to_embed_text() for k in parcalar])
    norm = np.linalg.norm(vektorler, axis=1, keepdims=True)
    norm[norm == 0] = 1.0

    VektorDeposu(KARAR_INDEX_DIR).kaydet(
        [k.to_dict() for k in parcalar], vektorler / norm)
    log.info("karar indeksi hazir: %d parca -> %s", len(parcalar), KARAR_INDEX_DIR)


def cmd_bm25(args) -> None:
    """Yalnizca BM25 indeksini yeniden kurar.

    Gomme saatler suruyor; BM25 dakikalar. Ikisini ayirmak sart cunku BM25
    adimi bellek yuzunden ayrica cokebiliyor ve o zaman gommeyi bastan
    yapmak sacma olur.
    """
    from core.embedder import Embedder
    from core.retrieve import Retriever
    from core.vektor import VektorDeposu

    store = VektorDeposu()
    # Embedder modeli tembel yukluyor; BM25 icin GPU'ya hic gidilmez.
    Retriever(store, Embedder()).bm25_kur()


def cmd_indeksle(args) -> None:
    import gc

    from core.embedder import Embedder
    from core.retrieve import Retriever

    if not MADDE_YOLU.exists():
        sys.exit("Once 'python cli.py cek' calistirin.")
    maddeler = json.loads(MADDE_YOLU.read_text(encoding="utf-8"))
    log.info("%d madde yuklendi", len(maddeler))

    metinler = [_embed_metni(m) for m in maddeler]

    # Degismeyen maddeyi yeniden gommek gereksiz. 275 bin maddeyi bastan
    # gommek RTX 3050'de saatler suruyor, oysa bir ayristirici duzeltmesi
    # tipik olarak maddelerin kucuk bir bolumunu degistiriyor. Anahtar
    # embed metninin KENDISI: madde numarasi degisse bile metin ayniysa
    # onceki vektor gecerlidir.
    satirlar, maske = (None, None) if args.tam else _onceki_vektorler(metinler)

    emb = Embedder()
    if maske is not None and maske.any():
        eksik = [j for j in range(len(metinler)) if not maske[j]]
        log.info("degismeyen %d madde onceki indeksten alindi, %d madde gomulecek",
                 int(maske.sum()), len(eksik))
        if eksik:
            log.info("embedding basliyor (cihaz: %s)...", emb.device)
            satirlar[eksik] = emb.encode_documents([metinler[j] for j in eksik])
        vektorler = satirlar
    else:
        log.info("embedding basliyor (cihaz: %s)...", emb.device)
        vektorler = emb.encode_documents(metinler)
    log.info("embedding bitti: %s", vektorler.shape)

    # Vektorler normalize edilir: kosinus benzerligi tek matris carpimina
    # inecek. Qdrant gomulu modda 174 bin noktada sorgu basina 2970 ms
    # tutuyordu, matris carpimi 46 ms.
    from core.vektor import VektorDeposu
    import numpy as np

    norm = np.linalg.norm(vektorler, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    store = VektorDeposu()
    store.kaydet(maddeler, vektorler / norm)

    from core.yazim import sozluk_kur
    sozluk_kur(maddeler)

    # BM25 kurulumu 275 bin dokumanda bellegin tepesini zorluyor. Buyuk
    # dizileri once birakiyoruz: onceki calismada pickle.dump MemoryError
    # verdi ve yarim yazilan bm25.pkl aramanin BM25 yarisini tumuyle bozdu.
    del vektorler, satirlar, maddeler, metinler, norm
    gc.collect()

    Retriever(store, emb).bm25_kur()
    log.info("indeks hazir: %d madde", store.sayi())


def _onceki_vektorler(metinler: list[str]):
    """Onceki indeksten, embed metni degismemis maddelerin vektorunu getirir.

    Doner: (matris, maske). Maske True olan satirlar dolu; False olanlar
    yeniden gomulecek. Onceki indeks yoksa (None, None) doner.
    """
    import numpy as np

    vyol = config.INDEX_DIR / "vektorler.npy"
    kyol = config.INDEX_DIR / "kayitlar.json"
    if not (vyol.exists() and kyol.exists()):
        return None, None
    eski_kayit = json.loads(kyol.read_text(encoding="utf-8"))
    # mmap: eski matris 1.13 GB. Tumuyle bellege almak gereksiz, yalnizca
    # yeniden kullanilan satirlar kopyalanacak. Bellek tepesini bu kadar
    # dusuruyor -- indeksleme bir kez MemoryError ile cokmustu.
    eski_vek = np.load(vyol, mmap_mode="r")
    if len(eski_kayit) != len(eski_vek):
        log.warning("onceki indeks tutarsiz, bastan gomulecek")
        return None, None

    dizin: dict[str, int] = {}
    for i, kayit in enumerate(eski_kayit):
        dizin.setdefault(_embed_metni(kayit), i)
    del eski_kayit          # 275 bin kayitlik liste; vektor matrisi zaten 1.1 GB

    satirlar = np.zeros((len(metinler), eski_vek.shape[1]), dtype=np.float32)
    maske = np.zeros(len(metinler), dtype=bool)
    for j, metin in enumerate(metinler):
        i = dizin.get(metin)
        if i is not None:
            satirlar[j] = eski_vek[i]
            maske[j] = True
    return satirlar, maske


def _embed_metni(m: dict) -> str:
    parcalar = [m.get("mevzuat_adi", "")]
    if m.get("bolum"):
        parcalar.append(m["bolum"])
    parcalar.append(f"Madde {m.get('madde_no','')}")
    if m.get("baslik"):
        parcalar.append(m["baslik"])
    parcalar.append(m.get("metin", ""))
    return "\n".join(p for p in parcalar if p)


def cmd_sor(args) -> None:
    from core.embedder import Embedder
    from core.vektor import VektorDeposu
    from core.retrieve import Retriever
    from core.generate import Generator

    store = VektorDeposu()
    r = Retriever(store, Embedder())
    maddeler = r.ara(args.soru, limit=args.k)

    print("\n=== BULUNAN MADDELER ===")
    for m in maddeler:
        print(f"  [{m['skor']:.4f}] {m['mevzuat_adi'][:45]} m.{m['madde_no']}"
              f" - {m.get('baslik','')[:45]}  ({','.join(m['kaynaklar'])})")

    if not args.sadece_arama:
        print("\n=== CEVAP ===")
        print(Generator().cevapla(args.soru, maddeler))
    store.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Turk mevzuati uzerinde yerel RAG")
    alt = p.add_subparsers(dest="komut", required=True)

    a = alt.add_parser("katalog", help="mevzuat listesini cek")
    a.add_argument("--tur", type=int, nargs="+", default=[1])
    a.add_argument("--limit", type=int, default=None)
    a.add_argument("--sifirdan", action="store_true",
                   help="mevcut katalogu koruma, bastan yaz")
    a.set_defaults(func=cmd_katalog)

    b = alt.add_parser("cek", help="metinleri indir ve madde JSON'a cevir")
    b.add_argument("--pilot", action="store_true", help="sadece 6 temel kanun")
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--sifirdan", action="store_true",
                   help="mevcut maddeleri koruma, bastan yaz")
    b.add_argument("--yenile-tur", type=int, nargs="+", default=None,
                   help="bu turleri, indirilmis olsalar da yeniden cek")
    b.add_argument("--baslangic", type=int, default=0,
                   help="katalogda ilk N belgeyi atla (yarim kalan isi surdurur)")
    b.set_defaults(func=cmd_cek)

    c = alt.add_parser("indeksle", help="GPU'da embed et, Qdrant + BM25 kur")
    c.add_argument("--tam", action="store_true",
                   help="degismeyenleri de yeniden gom (varsayilan: artimli)")
    c.set_defaults(func=cmd_indeksle)

    cb = alt.add_parser("bm25", help="yalnizca BM25 indeksini yeniden kur")
    cb.set_defaults(func=cmd_bm25)

    ki = alt.add_parser("karar-indeksle", help="kararlari ayri indekse yaz")
    ki.set_defaults(func=cmd_karar_indeksle)

    dn = alt.add_parser("danistay", help="Danistay kararlarini indir")
    dn.add_argument("--anahtar", nargs="+", default=IDARI_ANAHTARLAR)
    dn.add_argument("--adet", type=int, default=200, help="anahtar basina karar")
    dn.add_argument("--gecikme", type=float, default=2.0)
    dn.set_defaults(func=cmd_danistay)

    e = alt.add_parser("ictihat", help="mahkeme kararlarini indir")
    e.add_argument("--anahtar", nargs="+", default=IS_HUKUKU_ANAHTARLARI)
    e.add_argument("--kira", action="store_true",
                   help="kira hukuku kararlarini indir")
    e.add_argument("--adet", type=int, default=500, help="anahtar basina karar")
    e.add_argument("--gecikme", type=float, default=2.0)
    e.set_defaults(func=cmd_ictihat)

    d = alt.add_parser("sor", help="soru sor")
    d.add_argument("soru")
    d.add_argument("-k", type=int, default=5)
    d.add_argument("--sadece-arama", action="store_true", help="LLM'i atla")
    d.set_defaults(func=cmd_sor)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
