"""Avukat kendi eski dilekcesini bulabiliyor mu?

    .venv\\Scripts\\python olcum_arsiv.py

OLCULEN SORU

Buro arsivinde N dilekce var. Avukat "savunma alinmadan fesih"
yaziyor. O konudaki dilekceleri getirebiliyor muyuz?

Bu MEVZUAT ARAMASINDAN FARKLI bir olcu ister. Mevzuatta tek bir dogru
madde var ve birinci sirada olmasi onemli. Arsivde ayni konuda birden
fazla dosya var ve avukat hepsini gormek istiyor; birinci sira degil
ILK 10'DA OLMAK yetiyor.

  ilk-1     : en az bir dogru belge birinci sirada mi
  kapsama@5 : o konudaki belgelerin kaci ilk 5'te
  kapsama@10: kaci ilk 10'da
  MRR       : ilk dogru belgenin sira degerinin tersi

KIYAS

Vektor aramasi tek basina da olculuyor. RRF (vektor + BM25) gercekten
kazandiriyor mu, yoksa karmasikligi bosuna mi tasiyoruz -- mevzuatta
kazandirmisti ama burada belge duzeyinde topluyoruz, ayni sonuc
verecegi kesin degil.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

import config
from core.arsiv import Arsiv
from core.embedder import Embedder

logging.basicConfig(level=logging.ERROR)

KAYNAK = config.ROOT / "data" / "dilekce_deneme"

# Konu kodu -> avukatin yazacagi arama sorgusu. Bilerek dilekcedeki
# cumlelerden FARKLI yazildi; kelime eslesmesini degil anlam
# eslesmesini olcmek istiyoruz.
SORGULAR = {
    "is-savunma": "işçiye savunma hakkı verilmeden yapılan fesih",
    "is-ihbar": "ihbar öneli kullandırılmadan çıkarılan işçinin tazminatı",
    "is-fazlacalisma": "mesai ücretleri ödenmeyen işçi alacağı",
    "is-yillikizin": "izin kullandırılmayan işçinin izin ücreti",
    "is-mobbing": "işyerinde baskı ve yıldırma nedeniyle istifa",
    "is-kazasi": "çalışırken yaralanan işçinin tazminat talebi",
    "is-sendika": "sendikaya üye olduğu için işten çıkarılma",
    "kira-temerrut": "kirasını ödemeyen kiracının çıkarılması",
    "kira-ihtiyac": "ev sahibinin oturma ihtiyacı nedeniyle tahliye",
    "kira-tespit": "kira artış oranının mahkemece belirlenmesi",
    "kira-tahliyetaah": "yazılı taahhüde rağmen taşınmayan kiracı",
    "bos-siddetli": "geçimsizlik nedeniyle boşanma talebi",
    "bos-zina": "eşin sadakatsizliği nedeniyle boşanma",
    "bos-nafaka": "nafaka miktarının yükseltilmesi",
    "bos-velayet": "çocuğun velayetinin diğer ebeveyne geçmesi",
    "mir-tapuiptal": "mirastan mal kaçırmak için yapılan devrin iptali",
    "mir-tenkis": "saklı pay sahibinin payının geri alınması",
    "mir-ret": "borçlu ölenin mirasının reddi",
    "tic-cek": "karşılığı çıkmayan çek nedeniyle alacak",
    "tic-haksizrekabet": "rakip firmanın haksız ticari davranışı",
    "tic-ortaklik": "şirket ortağının ortaklıktan çıkarılması",
    "tuk-ayipli": "arızalı çıkan ürünün parasının geri alınması",
    "tuk-cayma": "internetten alınan üründen vazgeçme hakkı",
    "cez-hakaret": "sözle onur kırıcı davranış nedeniyle şikâyet",
    "cez-dolandiricilik": "kandırarak para alınması suçu",
    "cez-yaralama": "darp sonucu yaralanma şikâyeti",
    "cez-tehdit": "korkutma ve para isteme suçu",
    "idr-disiplin": "memura verilen cezanın iptali istemi",
    "idr-atama": "başka ile tayin işleminin iptali",
    "idr-imar": "belediyenin plan değişikliğine karşı dava",
    "idr-vergi": "kesilen vergi cezasının kaldırılması",
    "icr-itiraz": "borçlunun takibe itirazının kaldırılması",
    "icr-istihkak": "haczedilen eşyanın başkasına ait olması",
    "bor-haksizfiil": "araç çarpması sonucu zararın tazmini",
    "bor-sebepsiz": "haksız yere alınan paranın geri istenmesi",
    "bor-genelislem": "sözleşmeye tek taraflı konulan hükmün geçersizliği",
    "kvk-silme": "verilerimin silinmesi talebinin reddedilmesi",
    "fik-marka": "başkasının markasının iptali",
    "gay-elatma": "komşunun taşınmaza tecavüzünün önlenmesi",
    "gay-ortaklik": "paylı taşınmazın satışla paylaştırılması",
}


# Avukat gercekte boyle aramaz. Yukaridaki sorgular fazla temiz ve
# odakli; sahada cumle sudur: "hani bir dilekcemiz vardi, sundan
# bahsetmistim ya". Dolgu kelime, belirsiz gonderme, bazen yanlis
# terim. Ayni konular, konusma diliyle:
KONUSMA_SORGULARI = {
    "is-savunma": "hani bir dosya vardı işçinin savunmasını almadan atmışlardı ya onu bulabilir miyim",
    "is-ihbar": "şu adamı birden kovmuşlardı önceden haber vermeden, tazminat istemiştik",
    "is-fazlacalisma": "işçi sürekli fazla çalışıyordu ama parasını vermiyorlardı hani",
    "is-yillikizin": "adam yıllarca izin kullanamamıştı o dilekçe",
    "is-mobbing": "kadına işyerinde çok baskı yapmışlardı o yüzden ayrılmıştı",
    "is-kazasi": "iş yerinde kaza geçiren adamın dosyası vardı ya",
    "is-sendika": "sendikaya girdiği için atmışlardı adamı",
    "kira-temerrut": "kiracı kira ödemiyordu çıkarmak istemiştik o dilekçe",
    "kira-ihtiyac": "ev sahibi kendisi oturacaktı o yüzden tahliye istemiştik",
    "kira-tespit": "kira ne kadar olacak diye mahkemeye sormuştuk hani",
    "kira-tahliyetaah": "çıkacağım demişti yazılı vermişti ama çıkmadı",
    "bos-siddetli": "şu boşanma dosyası vardı ya hiç anlaşamıyorlardı",
    "bos-zina": "adam eşini aldatmıştı o boşanma davası",
    "bos-nafaka": "nafaka az geliyordu artırmak istemiştik",
    "bos-velayet": "çocuk babada kalıyordu anneye almak istemiştik",
    "mir-tapuiptal": "ölmeden önce tapuyu birine devretmişti diğerleri mağdur olmuştu",
    "mir-tenkis": "mirasta payını alamayan bir müvekkil vardı",
    "mir-ret": "adamın borcu vardı öldü mirasçılar kabul etmek istemedi",
    "tic-cek": "çek yazmıştı karşılığı çıkmadı",
    "tic-haksizrekabet": "rakip firma bizim müşterileri çalıyordu hani",
    "tic-ortaklik": "şirketten ortağı çıkarmak istemişlerdi",
    "tuk-ayipli": "aldığı ürün bozuk çıkmıştı parasını geri istiyordu",
    "tuk-cayma": "internetten almıştı vazgeçmek istedi vermediler",
    "cez-hakaret": "adama küfür etmişlerdi şikayetçi olmuştuk",
    "cez-dolandiricilik": "adamı kandırıp parasını almışlardı o şikayet dilekçesi",
    "cez-yaralama": "kavgada dövmüşlerdi müvekkili",
    "cez-tehdit": "tehdit edip para istemişlerdi ondan şikayetçi olmuştuk",
    "idr-disiplin": "memura ceza vermişlerdi iptal ettirmek istemiştik",
    "idr-atama": "başka şehre sürmüşlerdi memuru",
    "idr-imar": "belediye imar planını değiştirmişti dava açmıştık",
    "idr-vergi": "vergi cezası kesmişlerdi kaldırtmak istemiştik",
    "icr-itiraz": "borçlu takibe itiraz etmişti biz de itirazın iptalini istemiştik",
    "icr-istihkak": "haczettikleri eşya aslında başkasınındı",
    "bor-haksizfiil": "trafik kazası olmuştu tazminat istemiştik hani",
    "bor-sebepsiz": "yanlışlıkla fazla para gitmişti geri istiyorduk",
    "bor-genelislem": "sözleşmeye küçük harflerle bir madde koymuşlardı geçersiz saydırmak istedik",
    "kvk-silme": "verilerimi silin demişti şirket silmemişti",
    "fik-marka": "bizim markaya benzer marka almışlardı iptal ettirecektik",
    "gay-elatma": "komşu duvarı bizim araziye taşımıştı",
    "gay-ortaklik": "ortak tarlayı satıp bölüşmek istiyorlardı",
}


def belgeleri_oku() -> tuple[dict[str, str], dict[str, str]]:
    """(belge_adi -> metin, belge_adi -> konu_kodu)"""
    etiketler = json.loads((KAYNAK / "konular.json").read_text("utf-8"))
    metinler, konular = {}, {}
    for yol in sorted(KAYNAK.glob("*.txt")):
        bilgi = etiketler.get(yol.name)
        if not bilgi:
            continue
        metinler[yol.name] = yol.read_text("utf-8")
        konular[yol.name] = bilgi["konu_kodu"]
    return metinler, konular


def _vektor_ara(arsiv: Arsiv, soru: str, limit: int) -> list[str]:
    """Yalnizca vektor benzerligiyle, belge duzeyinde siralama."""
    sorgu = np.asarray(arsiv.embedder.encode_query(soru),
                       dtype=np.float32).reshape(-1)
    benzerlik = arsiv._vektorler @ sorgu
    en_iyi: dict[str, float] = {}
    for i in np.argsort(-benzerlik)[:200]:
        ad = arsiv._parcalar[int(i)]["belge"]
        if ad not in en_iyi:
            en_iyi[ad] = float(benzerlik[int(i)])
    return [a for a, _ in sorted(en_iyi.items(), key=lambda x: -x[1])][:limit]


def olc(siralamalar: dict[str, list[str]], konular: dict[str, str],
        konu_belgeleri: dict[str, list[str]]) -> dict:
    ilk1 = kap5 = kap10 = vurus5 = 0
    toplam_dogru = 0
    mrr = 0.0
    for kod, sira in siralamalar.items():
        dogrular = set(konu_belgeleri[kod])
        toplam_dogru += len(dogrular)
        kap5 += sum(1 for b in sira[:5] if b in dogrular)
        kap10 += sum(1 for b in sira[:10] if b in dogrular)
        # Avukatin sordugu soru bu: "aradigim dilekce ilk 5'te var mi".
        # Hepsinin degil, EN AZ BIRININ cikmasi yetiyor -- ekranda
        # alintisini gorup taniyacak.
        if any(b in dogrular for b in sira[:5]):
            vurus5 += 1
        if sira and sira[0] in dogrular:
            ilk1 += 1
        for yer, b in enumerate(sira, 1):
            if b in dogrular:
                mrr += 1 / yer
                break
    n = len(siralamalar)
    return {"n": n, "ilk1": ilk1, "vurus5": vurus5, "kap5": kap5, "kap10": kap10,
            "toplam": toplam_dogru, "mrr": mrr / n if n else 0.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--cikti", default=None)
    args = ap.parse_args()

    metinler, konular = belgeleri_oku()
    konu_belgeleri: dict[str, list[str]] = defaultdict(list)
    for ad, kod in konular.items():
        konu_belgeleri[kod].append(ad)

    out = io.StringIO()
    out.write("ARSIV ARAMASI OLCUMU\n")
    out.write("%d belge, %d konu, %d sorgu\n" % (
        len(metinler), len(konu_belgeleri), len(SORGULAR)))

    arsiv = Arsiv(Embedder())
    t = time.time()
    parca = arsiv.indeksle(metinler, goster=False)
    out.write("indeksleme: %d parca, %.1f sn (yerel, bulut cagrisi yok)\n"
              % (parca, time.time() - t))

    hibrit: dict[str, list[str]] = {}
    yalniz_vektor: dict[str, list[str]] = {}
    konusma: dict[str, list[str]] = {}
    t = time.time()
    for kod, soru in SORGULAR.items():
        if kod not in konu_belgeleri:
            continue
        hibrit[kod] = [s["belge"] for s in arsiv.ara(soru, limit=args.limit)]
        yalniz_vektor[kod] = _vektor_ara(arsiv, soru, args.limit)
    sure = time.time() - t
    konusma_ham: dict[str, list[str]] = {}
    konusma_vektor: dict[str, list[str]] = {}
    for kod, soru in KONUSMA_SORGULARI.items():
        if kod not in konu_belgeleri:
            continue
        # sadelestir=False: dolgu kelimeler atilmadan, ham haliyle
        konusma_ham[kod] = [s["belge"] for s in
                            arsiv.ara(soru, limit=args.limit, sadelestir=False)]
        konusma[kod] = [s["belge"] for s in arsiv.ara(soru, limit=args.limit)]
        from core.arsiv import sorguyu_sadelestir
        konusma_vektor[kod] = _vektor_ara(
            arsiv, sorguyu_sadelestir(soru), args.limit)

    out.write("\n%s\n%-24s %-30s %s\n%s\n" % ("=" * 96, "konu", "sorgu",
                                              "ilk 10'daki dogrular", "-" * 96))
    for kod in hibrit:
        dogrular = set(konu_belgeleri[kod])
        yerler = [str(i) for i, b in enumerate(hibrit[kod], 1) if b in dogrular]
        out.write("%-24s %-30s %s/%d  siralar: %s\n" % (
            kod, SORGULAR[kod][:30], len(yerler), len(dogrular),
            ",".join(yerler) or "-"))

    a = olc(hibrit, konular, konu_belgeleri)
    b = olc(yalniz_vektor, konular, konu_belgeleri)

    out.write("\n%s\nSONUC\n%s\n" % ("=" * 96, "=" * 96))
    out.write("%-22s %8s %11s %11s %12s %7s\n" % (
        "yontem", "ilk-1", "ilk5te var", "kapsama@5", "kapsama@10", "MRR"))
    out.write("-" * 96 + "\n")
    c = olc(konusma, konular, konu_belgeleri)
    d = olc(konusma_ham, konular, konu_belgeleri)
    e = olc(konusma_vektor, konular, konu_belgeleri)
    for ad, s in (("temiz: hibrit", a), ("temiz: vektor", b),
                  ("konusma: ham", d), ("konusma: hibrit+sade", c),
                  ("konusma: vektor+sade", e)):
        out.write("%-22s %5d/%-2d %7d/%-3d %6d/%-4d %7d/%-4d %7.3f\n" % (
            ad, s["ilk1"], s["n"], s["vurus5"], s["n"], s["kap5"],
            s["toplam"], s["kap10"], s["toplam"], s["mrr"]))
    out.write("\nsorgu basina sure: %.2f sn (yeniden siralayici YOK)\n"
              % (sure / max(len(hibrit), 1)))

    metin = out.getvalue()
    print(metin)
    if args.cikti:
        Path(args.cikti).write_text(metin, encoding="utf-8")


if __name__ == "__main__":
    main()
