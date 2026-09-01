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

    # Mevcut veriyi koru: cek komutu daha once dosyayi bastan yaziyordu ve
    # eksikleri tamamlamak icin calistirildiginda onceki her seyi siliyordu.
    mevcut: dict[str, dict] = {}
    if not args.sifirdan and MADDE_YOLU.exists():
        for m in json.loads(MADDE_YOLU.read_text(encoding="utf-8")):
            mevcut[m["chunk_id"]] = m
        log.info("mevcut %d madde korunuyor", len(mevcut))

    def kaydet(yeniler: list[dict]) -> None:
        birlesik = dict(mevcut)
        for m in yeniler:
            birlesik[m["chunk_id"]] = m
        MADDE_YOLU.write_text(
            json.dumps(list(birlesik.values()), ensure_ascii=False, indent=1),
            encoding="utf-8")

    # Zaten indirilmis belgeleri atla. --yenile-tur ile verilen turler
    # atlanmaz: PDF adresi ya da ayristirici duzeldiginde o turleri yeniden
    # cekmek gerekiyor (eski kayitlar HTML'den gelmis olabilir; HTML uzun
    # belgeleri sessizce kesiyor).
    yenilenecek = set(args.yenile_tur or ())
    islenmis = {(m["mevzuat_no"], m["tertip"], m["mevzuat_tur"])
                for m in mevcut.values()}

    tum_maddeler, basarisiz = [], []
    for i, (no, tur, tertip, ad, pdf_url, metinsiz) in enumerate(hedefler, 1):
        # Tum kulliyat ~40 dakika suruyor. Sadece sonda kaydedersek 900. kanunda
        # olusan bir hata butun isi cope atar; araligi kacirmamak icin arada
        # diske yaziyoruz. PDF'ler zaten onbellekte, tekrar calistirmak ucuz.
        if i % 50 == 0:
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


# Demo icin secilen alan: is hukuku. Sebebi, Is Kanunu'nun zaten indekste
# olmasi -- "kanun + karar" birlesimini gosterebilecegimiz tek alan bu.
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

KARAR_YOLU = config.RAW_DIR / "kararlar.json"


def cmd_ictihat(args) -> None:
    from scraper.ictihat import EmsalClient

    istemci = EmsalClient(delay=args.gecikme)
    hepsi: dict[str, dict] = {}

    if KARAR_YOLU.exists():          # yarim kalmis indirmeyi surdur
        for k in json.loads(KARAR_YOLU.read_text(encoding="utf-8")):
            hepsi[k["id"]] = k
        log.info("%d karar zaten var, uzerine ekleniyor", len(hepsi))

    def kaydet() -> None:
        KARAR_YOLU.write_text(
            json.dumps(list(hepsi.values()), ensure_ascii=False, indent=1),
            encoding="utf-8")

    for kelime in args.anahtar:
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
    log.info("%d karar yuklendi", len(ham))

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


def cmd_indeksle(args) -> None:
    from core.embedder import Embedder
    from core.retrieve import Retriever

    if not MADDE_YOLU.exists():
        sys.exit("Once 'python cli.py cek' calistirin.")
    maddeler = json.loads(MADDE_YOLU.read_text(encoding="utf-8"))
    log.info("%d madde yuklendi", len(maddeler))

    emb = Embedder()
    metinler = [_embed_metni(m) for m in maddeler]
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

    Retriever(store, emb).bm25_kur()

    from core.yazim import sozluk_kur
    sozluk_kur(maddeler)
    log.info("indeks hazir: %d madde", store.sayi())


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
    b.set_defaults(func=cmd_cek)

    c = alt.add_parser("indeksle", help="GPU'da embed et, Qdrant + BM25 kur")
    c.set_defaults(func=cmd_indeksle)

    ki = alt.add_parser("karar-indeksle", help="kararlari ayri indekse yaz")
    ki.set_defaults(func=cmd_karar_indeksle)

    e = alt.add_parser("ictihat", help="mahkeme kararlarini indir")
    e.add_argument("--anahtar", nargs="+", default=IS_HUKUKU_ANAHTARLARI)
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
