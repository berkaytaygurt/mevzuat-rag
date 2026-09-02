"""Mevzuat metnini madde bazli yapiya cevirir.

KAYNAK SECIMI: Birincil kaynak PDF'tir. Sitenin iframe HTML'i uzun kanunlari
sessizce kesiyor (TMK'nin 1030 maddesinden yalnizca 425'ini, TBK'nin 649'undan
481'ini veriyor) ve metnin bir kisminda cift-encode bozulmasi tasiyor. Ayni
kanunlarin PDF'i tam ve temiz geliyor. HTML yolu yedek olarak duruyor.

CHUNKING: Her madde bir chunk. Hukuk metni zaten maddelere bolunmus durumda;
sabit karakter sayisiyla kesmek madde butunlugunu ve cevabin dayanagini bozar.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, asdict, field

# "Madde 1 -", "MADDE 12 –", "Ek Madde 3 -", "Gecici Madde 2 -", "Madde 3/A-"
#
# Harf ekli maddeler ayri hukumdur ve avukat onlari "2576 m.3/A" diye anar.
# Harf yakalanmazken hepsi ayni numaraya dusuyor, ayristirici da cakismayi
# "3 (2)", "3 (9)" diye ciftliyordu -- kimsenin arayamayacagi bir ad. Bu
# durumdaki madde sayisi olculdu: 1.740 (374'u kanunlarda).
MADDE_RE = re.compile(
    r"^\s*(?P<tip>Ek|Geçici|Gecici|Mükerrer|Mukerrer)?\s*Madde\s+(?P<no>\d+)"
    r"(?:\s*/\s*(?P<harf>[A-ZÇĞİÖŞÜ]))?\s*[-–—]?\s*",
    re.IGNORECASE,
)
BOLUM_RE = re.compile(
    r"^\s*[A-ZÇĞİÖŞÜ\s]{3,}\s+(BÖLÜM|KISIM|AYIRIM|AYRIM|KİTAP)\s*$", re.IGNORECASE
)
DEGISIKLIK_RE = re.compile(r"\((?:Ek|Değişik|Degisik|Mülga|Mulga|İptal|Iptal)\s*:[^)]{0,200}\)")
MULGA_RE = re.compile(r"\(\s*(?:Mülga|Mulga|İptal|Iptal)\s*:", re.IGNORECASE)
# Maddenin TAMAMI mulga ise isaret metnin en basinda durur. Isaret govdenin
# icinde geciyorsa yalnizca bir fikra kaldirilmistir ve madde yururluktedir
# (or. KVKK m.6: 2. fikra 2024'te mulga, madde yururlukte). Ikisini ayirmazsak
# yururlukteki madde varsayilan aramadan tamamen dusuyor.
TAM_MULGA_RE = re.compile(r"^\s*\(\s*(?:Mülga|Mulga|İptal|Iptal)\s*:", re.IGNORECASE)
# Belge sonundaki degisiklik listesi -- asil metin burada biter
SON_RE = re.compile(
    r"(EK\s+VE\s+DEĞİŞİKLİK\s+GETİREN|YÜRÜRLÜĞE\s+GİRİŞ\s+TARİHLERİNİ\s+GÖSTERİR"
    r"|İŞLENEMEYEN\s+HÜKÜMLER)", re.IGNORECASE)
DIPNOT_RE = re.compile(r"^\s*\(?\[?\d{1,3}\]?\)?\s+(?=\d{1,2}/\d{1,2}/\d{4}\s+tarihli)")
# Baslik olamayacak satirlar: "a) ...", "(2) ..." gibi fikra/bent isaretleri
GECERSIZ_BASLIK_RE = re.compile(r"^\s*(?:[a-zçğıöşü]\)|\d+\)|\()")


@dataclass
class Madde:
    mevzuat_no: str
    mevzuat_adi: str
    mevzuat_tur: str
    tertip: str
    madde_no: str
    baslik: str
    metin: str
    bolum: str = ""
    degisiklikler: list[str] = field(default_factory=list)
    mulga: bool = False          # maddenin tamami yururlukten kalkti
    kismi_mulga: bool = False    # yalnizca bir fikrasi kaldirildi

    @property
    def chunk_id(self) -> str:
        # Tertip sart: ayni numarayi tasiyan farkli kanunlar var (6551 hem
        # Tertip 3 "Barut ve Patlayici Maddeler" hem Tertip 5 "Terorun Sona
        # Erdirilmesi"). Tertipsiz id'de maddeleri cakisip birbirini eziyor;
        # tam kulliyatta 104 madde bu yuzden indekse hic girmemisti.
        return (f"{self.mevzuat_tur}-{self.mevzuat_no}-{self.tertip}-{self.madde_no}"
                .replace(" ", "_").replace("/", "_"))

    def to_embed_text(self) -> str:
        """Embedding'e verilecek metin. Kanun adi ve baslik da dahil ki
        'yillik izin' sorgusu, ifade govdede gecmese bile eslesebilsin."""
        parcalar = [self.mevzuat_adi]
        if self.bolum:
            parcalar.append(self.bolum)
        parcalar.append(f"Madde {self.madde_no}")
        if self.baslik:
            parcalar.append(self.baslik)
        parcalar.append(self.metin)
        return "\n".join(p for p in parcalar if p)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunk_id"] = self.chunk_id
        return d


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _baslik_olabilir(satir: str) -> bool:
    """Bir satirin madde basligi olup olamayacagini karara baglar.

    Madde basligi, madde satirindan hemen onceki satirdir. Ama onceki maddenin
    metni bir cumleyle bittiyse o cumlenin son satiri baslik sanilir. Olculdu:
    kanunlarin %19.5'inde baslik "eklenmiştir.", "yürürlüğe girer." gibi cumle
    parcasiydi. Gercek madde basliklari ("Amaç ve kapsam", "Yıllık ücretli
    izin hakkı") nokta ile bitmez -- 16 rastgele ornekte istisna bulunamadi.

    Yanlis baslik zararsiz degil: BM25 metninde uc kez tekrarlaniyor ve
    indeksi zehirliyor. Bos birakmak dogru cevap.
    """
    if not satir or len(satir) > 90:
        return False
    kirpik = satir.rstrip()
    if MADDE_RE.match(satir) or BOLUM_RE.match(satir):
        return False
    if GECERSIZ_BASLIK_RE.match(satir):
        return False
    if kirpik.endswith((",", ";", ".")):
        return False
    if kirpik.startswith(":"):      # "  : Tertip: 3 Cilt: 30" gibi kunye satiri
        return False
    return True


# --------------------------------------------------------------------------
# Kaynaklardan blok listesi
# --------------------------------------------------------------------------
# Sayfa alti dipnotlari govde metninden kucuk punto ile diziliyor. Olculdu
# (4857 sayili Is Kanunu): govde 12.0 punto / 2024 satir, dipnot 11.0 punto /
# 117 satir -- ayrim kesin, tek istisna yok.
#
# Bu ayrimi kullanmak SART, cunku dipnot sayfa altinda maddenin IKI FIKRASI
# ARASINA dusuyor. Eski ayristirici dipnotu madde siniri sayip maddeyi orada
# kapatiyordu ve kalan fikralar tumuyle kayboluyordu: 4857 m.19 kulliyata
# 112 karakter olarak girmisti, "savunmasini almadan ... feshedilemez"
# fikrasi hic yoktu.
DIPNOT_PUNTO_PAYI = 0.4


def _pdf_satir_puntolari(pdf_baytlari: bytes) -> list[tuple[float, str]]:
    """PyMuPDF ile (punto, satir) ciftleri.

    Satirin puntosu icindeki EN BUYUK span'dir; boylece govde satirinin
    sonundaki ust-simge dipnot isareti satiri kucuk gostermez.
    """
    import pymupdf

    ciftler: list[tuple[float, str]] = []
    with pymupdf.open(stream=pdf_baytlari, filetype="pdf") as belge:
        for sayfa in belge:
            for blok in sayfa.get_text("dict")["blocks"]:
                for satir in blok.get("lines", []):
                    spanlar = satir.get("spans") or []
                    metin = _clean("".join(s["text"] for s in spanlar))
                    if metin and spanlar:
                        ciftler.append((max(s["size"] for s in spanlar), metin))
    return ciftler


def bloklar_pdf(pdf_baytlari: bytes) -> list[str]:
    """PDF -> satir listesi, sayfa alti dipnotlari ayiklanmis halde.

    Birincil cikarici PyMuPDF. pypdf bu belgelerde kelime ortasina bosluk
    sokuyor ("s ozlesmenin", "as ilanmasi v e nak li"): TMK'de her bin
    kelimede 12 bozuk token, TBK'de 8. PyMuPDF ayni belgelerde bu orani
    1.2'ye dusuruyor ve kalanlar mesru "o" zamiri. Bozuk tokenler BM25
    eslesmesini dogrudan kaybettirdigi icin bu fark onemli.
    """
    try:
        satirlar = _pdf_satir_puntolari(pdf_baytlari)
    except ImportError:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_baytlari))
        ham = "\n".join((s.extract_text() or "") for s in reader.pages)
        return [t for h in ham.split("\n") if (t := _clean(h))]

    if not satirlar:
        return []
    # Govde puntosu = en cok satirda kullanilan punto. Baslik satirlari
    # govdeden BUYUK oldugu icin bu esikte kalir; yalnizca kucuk punto
    # (dipnot) duser.
    govde_punto = Counter(p for p, _ in satirlar).most_common(1)[0][0]
    esik = govde_punto - DIPNOT_PUNTO_PAYI
    return [t for p, t in satirlar if p >= esik]


def bloklar_html(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    out = []
    for p in soup.find_all("p"):
        # Belge sonundaki degisiklik tablosu <table> icinde durur; hucreleri
        # tek tek paragraf gorunur ve madde sanilir.
        if p.find_parent("table"):
            continue
        if t := _clean(p.get_text(" ", strip=True)):
            out.append(t)
    return out


def _meta_cikar(bloklar: list[str]) -> dict:
    meta = {"ad": "", "no": "", "tertip": ""}
    for t in bloklar[:20]:
        if not meta["ad"] and ":" not in t and 3 < len(t) < 120:
            # Kanun adina yapisan dipnot isaretini at. HTML'de "[1]" olarak,
            # PDF'te ust-simge duz rakama dondugu icin "KANUNU1" olarak gelir.
            ad = re.sub(r"\s*\[\d+\]\s*$", "", t).strip()
            ad = re.sub(r"(?<=[A-ZÇĞİÖŞÜa-zçğıöşü])\d{1,3}$", "", ad).strip()
            meta["ad"] = ad
        if m := re.search(r"(?:Kanun|Mevzuat)\s*Numaras[ıi]\s*:\s*([\d/]+)", t, re.I):
            meta["no"] = m.group(1).strip()
        if m := re.search(r"Tertip\s*:\s*(\d+)", t, re.I):
            meta["tertip"] = m.group(1).strip()
    return meta


# --------------------------------------------------------------------------
# Ortak madde cikarma
# --------------------------------------------------------------------------
# Duz metin belgeler icin parca boyu. 1500 karakter, madde uzunluklarinin
# ust ceyregine denk geliyor; embedding modelinin 512 token penceresini de
# asmiyor.
_PARCA_BOYU = 1500


def _duz_metin_parcalari(bloklar: list[str], ad: str, tur_adi: str,
                         no: str, tert: str) -> list[Madde]:
    """Madde basligi tasimayan belgeleri paragraf paragraf boler.

    Teblig ve yonetmeliklerin buyuk bolumu numarali madde icermiyor; tek
    parca duz metin halinde yaziliyor. Madde arayan ayristirici bunlari bos
    donduruyor ve belge tumuyle kayboluyordu -- olculdu: yalnizca tebligde
    4.099 belge bu yuzden indekse hic girmemis.
    """
    metin = "\n".join(b.strip() for b in bloklar if b.strip())
    if len(metin) < 200:
        return []
    # Sunucunun bakim sayfasi 10.832 karakter metin tasiyor ve gercek belge
    # gibi gorunuyor; boyut kontrolunu asarsa burada yakalanir.
    if "Sayfada Çalışma Yapılmaktadır" in metin[:400]:
        return []

    parcalar: list[str] = []
    tampon = ""
    for paragraf in metin.split("\n"):
        if len(tampon) + len(paragraf) + 1 > _PARCA_BOYU and tampon:
            parcalar.append(tampon.strip())
            tampon = paragraf
        else:
            tampon = f"{tampon}\n{paragraf}" if tampon else paragraf
    if tampon.strip():
        parcalar.append(tampon.strip())

    # Ilk satir genelde belgenin basligi; parcalara ad olarak veriyoruz ki
    # arama sonucunda hangi belge oldugu gorunsun.
    ust_baslik = bloklar[0].strip()[:90] if bloklar else ad[:90]

    return [Madde(mevzuat_no=no, mevzuat_adi=ad, mevzuat_tur=tur_adi,
                  tertip=tert, madde_no=f"Metin {i}", baslik=ust_baslik,
                  metin=p, bolum="")
            for i, p in enumerate(parcalar, 1)]


def maddeleri_cikar(bloklar: list[str], *, tur_adi: str = "Kanun",
                    mevzuat_no: str = "", tertip: str = "") -> list[Madde]:
    if not bloklar:
        return []

    meta = _meta_cikar(bloklar)
    ad = meta["ad"] or "Bilinmeyen Mevzuat"
    no = mevzuat_no or meta["no"]
    tert = tertip or meta["tertip"]

    maddeler: list[Madde] = []
    dipnot_modu = False
    bolum = ""
    current: Madde | None = None
    govde: list[str] = []

    def flush() -> None:
        nonlocal current, govde
        if current is not None:
            current.metin = " ".join(govde).strip()
            current.degisiklikler = DEGISIKLIK_RE.findall(current.metin)
            current.mulga = bool(TAM_MULGA_RE.match(current.metin))
            current.kismi_mulga = (not current.mulga
                                   and bool(MULGA_RE.search(current.metin)))
            if current.metin:
                maddeler.append(current)
        current, govde = None, []

    for i, blok in enumerate(bloklar):
        if SON_RE.search(blok):
            flush()
            break
        # Dipnot madde SINIRI DEGIL. Burada eskiden flush() vardi; dipnot
        # sayfa altinda iki fikra arasina dustugu icin maddenin geri kalani
        # cope gidiyordu. PDF yolunda dipnotlar zaten punto farkiyla
        # ayiklaniyor -- bu dal HTML yolu ve punto ayrimi tasimayan
        # belgeler icin yedek.
        if DIPNOT_RE.match(blok):
            dipnot_modu = not blok.rstrip().endswith((".", "!", "?"))
            continue
        if dipnot_modu:
            if MADDE_RE.match(blok) or BOLUM_RE.match(blok):
                dipnot_modu = False      # dipnot kapanmadan yeni madde geldi
            else:
                dipnot_modu = not blok.rstrip().endswith((".", "!", "?"))
                continue

        if BOLUM_RE.match(blok):
            flush()
            alt = bloklar[i + 1] if i + 1 < len(bloklar) else ""
            bolum = f"{blok} - {alt}" if alt and len(alt) < 90 else blok
            continue

        if m := MADDE_RE.match(blok):
            onceki = bloklar[i - 1] if i > 0 else ""
            baslik = onceki if _baslik_olabilir(onceki) else ""
            # Baslik satiri bir onceki dongude onceki maddenin govdesine de
            # eklenmisti. Cikarilmazsa her maddenin metni BIR SONRAKI
            # maddenin basligiyla bitiyor (4857 m.19 "... saklidir. Fesih
            # bildirimine itiraz ve usulu" diye bitiyordu).
            #
            # Ama _baslik_olabilir kesin bir olcut degil: 6518 m.101'in
            # gercek son satiri "... yerine islenmistir.)" de baslik
            # goruntusu veriyor ve cikarilinca METIN KAYBEDIYORUZ. Bu yuzden
            # yalnizca bir onceki satir cumleyi bitirmisse -- yani govde
            # gercekten kapanmis, sonrasi ayri bir satir olarak duruyorsa --
            # cikariyoruz.
            onun_oncesi = bloklar[i - 2].rstrip() if i >= 2 else ""
            if (baslik and len(govde) > 1 and govde[-1] == onceki
                    and onun_oncesi.endswith((".", ")", "!", "?"))):
                govde.pop()
            flush()
            tip = (m.group("tip") or "").strip().title()
            tip = {"Gecici": "Geçici", "Mukerrer": "Mükerrer"}.get(tip, tip)
            harf = (m.group("harf") or "").upper()
            madde_no = f"{tip} {m.group('no')}".strip() + (f"/{harf}" if harf else "")
            # "1. Onemli sebepler2" -> sondaki dipnot rakamini at
            baslik = re.sub(r"(?<=[A-ZÇĞİÖŞÜa-zçğıöşü])\d{1,3}$", "", baslik).strip()

            current = Madde(mevzuat_no=no, mevzuat_adi=ad, mevzuat_tur=tur_adi,
                            tertip=tert, madde_no=madde_no, baslik=baslik,
                            metin="", bolum=bolum)
            govde = [blok[m.end():].strip()]
        elif current is not None:
            govde.append(blok)

    flush()

    # Madde basligi olmayan belge: tumuyle atmak yerine paragraflara bolup
    # saklariz.
    if not maddeler:
        maddeler = _duz_metin_parcalari(bloklar, ad, tur_adi, no, tert)

    # Ayni chunk_id iki kez olusursa vektor deposunda biri digerini ezer.
    gorulen: dict[str, int] = {}
    for m in maddeler:
        cid = m.chunk_id
        if cid in gorulen:
            gorulen[cid] += 1
            m.madde_no = f"{m.madde_no} ({gorulen[cid]})"
        else:
            gorulen[cid] = 1

    return maddeler


def parse_pdf(pdf_baytlari: bytes, **kw) -> list[Madde]:
    """PDF baytlarindan madde cikarir; bos girdide bos liste doner.

    Bos bayt istisna atarsa cagiran taraftaki HTML yedegi devreye girmiyor:
    istisna yakalanip belge dogrudan basarisiz sayiliyordu. Istemci artik
    sahte PDF'lerde bos bayt donduruyor, yani bu yol sik kullaniliyor.
    """
    if not pdf_baytlari:
        return []
    return maddeleri_cikar(bloklar_pdf(pdf_baytlari), **kw)


def parse_html(html: str, **kw) -> list[Madde]:
    return maddeleri_cikar(bloklar_html(html), **kw)
