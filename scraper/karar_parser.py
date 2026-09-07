"""Mahkeme karari metnini indekslenebilir parcalara ayirir.

Kanun metninde "her madde bir parca" dogal bir sinirdi. Karar metninde oyle bir
sinir yok: karar uzun bir anlatidir -- kunye, taraflarin iddialari, sonra
mahkemenin degerlendirmesi ve hukum.

ONCEKI YAKLASIM YANLISTI. Kod, gerekcenin "GEREĞİ DÜŞÜNÜLDÜ" ifadesiyle
basladigini varsayiyor ve docstring'i "incelenen kararlarin tamaminda bulundu"
diyordu. Indirilen 15 gercek kararda olculdu:

    GEREĞİ GÖRÜŞÜLDÜ                4/15
    GEREKÇE:                        3/15
    GEREĞİ DÜŞÜNÜLDÜ                0/15   <- kodun aradigi
    DELİLLERİN DEĞERLENDİRİLMESİ    0/15   <- notlarda onerilen duzeltme

Yani kararlarin cogunda boyle bir isaret yok; kod sessizce "metnin ikinci
yarisini al" yedegine dusuyordu ve gerekcenin basini kesiyordu.

Simdiki yaklasim isaret aramiyor: kunye satirlari (mahkeme adi, dava turu,
taraf bilgileri -- zaten anonimlestirilmis) atiliyor, kalan metin paragraf
sinirlarindan ~1500 karakterlik parcalara bolunuyor. Kararlarin ortanca
uzunlugu 4.844 karakter, yani karar basina 3-4 parca dusuyor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field

# Kararin basindaki kunye. Bilgi tasimiyor, indekste gurultu yaratiyor:
# taraf adlari anonimlestirilmis, dosya numaralari aramaya yaramiyor.
KUNYE_KALIPLARI = [
    # "İçtihat Metni" tek basina durabildigi gibi ardina T.C. de
    # eklenebiliyor (Danistay boyle veriyor); satir sonu sart degil.
    re.compile(r"^\s*\"?İçtihat Metni\"?\s*(T\.?C\.?)?\s*$", re.IGNORECASE),

    # --- DANISTAY KUNYESI ---
    # Danistay karari Yargitay'dan FARKLI bir baslikla basliyor ve
    # eski kaliplar bunu tanimiyordu. Sonuc olculdu: eleme modeli
    # metnin basini okudugu icin usul basligindan oteye gecemiyor ve
    # Danistay kararlari 0,03-0,17 alirken Yargitay kararlari 0,999
    # aliyordu -- ayni havuzda birlestirilince Danistay hep dibe
    # gomuluyordu.
    re.compile(r"^\s*Karar\s+İçeriği\s*$", re.IGNORECASE),
    re.compile(r"^\s*(DANIŞTAY|Danıştay).*\d{4}/\d+\s*E\.?.*$"),
    re.compile(r"^\s*(?:[A-ZÇĞİÖŞÜ]+\s+){0,3}DAİRES[İI]?\s*(BAŞKANLIĞI)?\s*$",
               re.IGNORECASE),
    re.compile(r"^\s*(?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|"
               r"YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|ONBİRİNCİ|ONİKİNCİ|"
               r"ONÜÇÜNCÜ|ONDÖRDÜNCÜ|ONBEŞİNCİ)\s+DAİRE\s*$", re.IGNORECASE),
    re.compile(r"^\s*İDAR[İI]\s+DAVA\s+DA[İI]RELER[İI]\s+KURULU\s*$",
               re.IGNORECASE),
    re.compile(r"^\s*(TEMYİZ\s+EDEN|KARŞI\s+TARAF|VEKİLİ|VEKİLLERİ|"
               r"MÜDAHİL|İSTEMİN\s+ÖZETİ)\b.*:.*$", re.IGNORECASE),
    re.compile(r"^\s*(YARGILAMA\s+SÜRECİ|DAVA\s+KONUSU\s+İSTEM)\s*:?\s*$",
               re.IGNORECASE),
    re.compile(r"^\s*(Mahkemesi|Dava Türü|Davacı|Davalı|Taraflar|Dava|İlgili Kanun)"
               r"\s*:.*$", re.IGNORECASE),
    re.compile(r"^\s*YARGITAY\s+(İLAMI|KARARI|\d+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\.\s*(Hukuk|Ceza)\s+Dairesi\s+\d{4}/\d+\s*E\..*$", re.IGNORECASE),
    # "Taraflar arasinda gorulen dava sonucunda verilen hukmun ... istenilmis"
    re.compile(r"^\s*Taraflar\s+arasında\s+görülen\s+dava.*$", re.IGNORECASE),
    # Harfleri bosluklu baslik: "Y A R G I T A Y   K A R A R I" (23 kararin
    # 17'sinde var). Duz metne cevrilince tek satir kaliyor.
    re.compile(r"^\s*(?:[A-ZÇĞİÖŞÜ]\s+){3,}[A-ZÇĞİÖŞÜ]\s*$"),
    # Dosya kunyesi: "TARİHİ : 08/12/2011", "NUMARASI : 2011/199-2011/1035"
    re.compile(r"^\s*(TAR[İI]H[İI]|NUMARASI|ESAS\s*NO|KARAR\s*NO|"
               r"[İI]LAM\s*NO)\s*:.*$", re.IGNORECASE),
    # Temyiz usul kalibi: hangi vekilin temyiz ettigi, raporun dinlendigi.
    # Her kararda ayni, bilgi tasimiyor.
    re.compile(r"^.*(temyiz\s+edilmiş\s+olmakla|Tetkik\s+Hakimi\s+tarafından\s+"
               r"düzenlenen\s+rapor).*$", re.IGNORECASE),
]
# Tek basina duran imza satirlari
IMZA_RE = re.compile(r"^\s*(BA[ŞS]KAN|[ÜU]YE|KAT[İI]P)\b.*$", re.IGNORECASE)
# "DAVACI : ...." gibi icerigi noktalarla doldurulmus bos alanlar
BOS_ALAN_RE = re.compile(r"^\s*[A-ZÇĞİÖŞÜ\s./]{3,40}\s*:\s*\.{0,4}\s*$")

# Parca boyu: mevzuat tarafiyla ayni (embedding penceresine sigiyor).
PARCA_BOYU = 1500
# Bundan kisa kalan metin indekse deger tasimiyor.
EN_AZ_METIN = 200


@dataclass
class Karar:
    karar_id: str
    daire: str
    esas_no: str
    karar_no: str
    karar_tarihi: str
    durum: str
    anahtar: str
    gerekce: str                 # indekslenen parca
    tam_metin: str               # kullaniciya gosterilen tam karar
    mahkeme: str = "Yargıtay"    # Danistay kararlari da ayni indekste
    parca_no: int = 1            # ayni karardan kacinci parca
    parca_adet: int = 1

    @property
    def chunk_id(self) -> str:
        # Parca numarasi sart: bir karardan birden fazla parca cikiyor ve
        # ayni id'yi tasirlarsa vektor deposunda biri digerini eziyor.
        return f"karar-{self.karar_id}-{self.parca_no}"

    @property
    def kisa_ad(self) -> str:
        """Kullaniciya gosterilen atif.

        MAHKEME ADI SART: Yargitay ve Danistay kararlari ayni listede
        gorunuyor ve daire adlari birbirine benziyor ("8. Daire" Danistay,
        "9. Hukuk Dairesi" Yargitay). Mahkeme yazilmayinca avukat hangi
        yargi kolundan bahsedildigini ayirt edemiyor.
        """
        daire = self.daire
        if self.mahkeme and not daire.startswith(self.mahkeme):
            daire = f"{self.mahkeme} {daire}".strip()
        ad = f"{daire} {self.esas_no} E. {self.karar_no} K.".strip()
        return f"{ad} ({self.parca_no}/{self.parca_adet})" if self.parca_adet > 1 else ad

    def to_embed_text(self) -> str:
        """Gomulecek metin. Daire adi ve anahtar da eklenir ki 'is hukuku'
        gibi genel bir sorgu, govdede o ifade gecmese bile eslesebilsin."""
        return "\n".join(p for p in [self.daire, self.anahtar, self.gerekce] if p)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunk_id"] = self.chunk_id
        d["kisa_ad"] = self.kisa_ad
        return d


def html_metne(ham: str) -> str:
    """Karar HTML'ini duz metne cevirir, satir yapisini koruyarak."""
    if not ham:
        return ""
    # IKI GECIS. Danistay belgeleri ic HTML'i KACISLI gonderiyor
    # (&lt;html&gt;&lt;head&gt;...). Tek gecis yapinca once etiketler
    # siliniyor, sonra kacislar cozulup etiketler metne GERI geliyordu ve
    # karar metni "<html><head><meta http-equiv=..." diye basliyordu.
    #
    # style/script GOVDESI de atilmali; yalnizca etiketi silmek yetmiyor,
    # icerigi metne karisiyor (".highlight { background-color: yellow; }").
    metin = ham
    for _ in range(2):
        metin = re.sub(r"<\s*(style|script)[^>]*>.*?<\s*/\s*\1\s*>", " ", metin,
                       flags=re.IGNORECASE | re.DOTALL)
        metin = re.sub(r"<\s*(br|/p|/div|/tr|/li)[^>]*>", "\n", metin,
                       flags=re.IGNORECASE)
        metin = re.sub(r"<[^>]+>", " ", metin)
        for kacan, karsilik in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                                ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'")):
            metin = metin.replace(kacan, karsilik)
        if "<" not in metin:
            break
    metin = re.sub(r"[ \t]+", " ", metin)
    return re.sub(r"\n\s*\n+", "\n", metin).strip()


def kunye_at(metin: str) -> str:
    """Kararin basindaki bilgi tasimayan satirlari atar."""
    tutulan = []
    for satir in metin.split("\n"):
        s = satir.strip()
        if not s:
            continue
        if IMZA_RE.match(s) or BOS_ALAN_RE.match(s):
            continue
        if any(k.match(s) for k in KUNYE_KALIPLARI):
            continue
        tutulan.append(s)
    return "\n".join(tutulan).strip()


# Danistay kararinda gerekcenin basladigi yer. Yargitay'da bu yaklasim
# DENENDI VE REDDEDILDI (yukaridaki modul aciklamasina bak: aranan isaret
# 15 kararin hicbirinde yoktu). Danistay FARKLI, olculdu -- onbellekteki
# 56 kararda:
#
#     GEREĞİ GÖRÜŞÜLDÜ        56/56   (%100)
#     HUKUKİ DEĞERLENDİRME    50/56   (%89)
#
# Yani burada isaret guvenilir. Ayni teknigin bir arsivde yanlis, otekinde
# dogru olmasi tuhaf degil: iki mahkemenin karar yazim gelenegi ayri.
DANISTAY_GEREKCE_RE = re.compile(
    r"(HUKUK[İI]\s+DE[ĞG]ERLEND[İI]RME|GERE[ĞG][İI]\s+G[ÖO]R[ÜU][ŞS][ÜU]LD[ÜU])",
    re.IGNORECASE)


def danistay_gerekce(metin: str) -> str:
    """Danistay kararinin USUL kismini atip gerekceden baslatir.

    NEDEN: Danistay karari uzun bir usul basligiyla basliyor ve icindeki
    isimler zaten "..." ile anonimlestirilmis:

        İSTEMİN KONUSU : ... Bölge İdare Mahkemesi ... tarih ve
        E:..., K:... sayılı ısrar kararının temyizen incelenerek
        bozulması istenilmektedir.

    Bu paragraflarda bilgi yok. Eleme modeli metnin BASINI okudugu icin
    ozu hic gormuyor ve alaka puani cok dusuk cikiyordu. Olculdu:

        ham metin              0,061
        kunye satirlari atik   0,537
        gerekceden baslat      asagida

    Isaret bulunamazsa metin OLDUGU GIBI doner -- kirpmak, yanlis yerden
    kirpmaktan iyidir.

    OLCULDU VE KULLANILMIYOR
    Ayni 12 karar uzerinde dort yontem karsilastirildi (alaka puani):

        yontem       en iyi   ilk 3'un ortalamasi
        ham metin     0,757        0,696
        kunye_at      0,845        0,769   <- SECILEN
        kunye + GG    0,968        0,584
        kunye + HD    0,696        0,444

    "Gerekceden baslat" TEK BIR kararda en yuksek puani aliyor (0,968)
    ama ILK UCUN ORTALAMASINI dusuruyor: birini kurtarip otekileri
    bozuyor. Avukata uc karar gosteriliyor, dolayisiyla dogru olcu
    ortalama -- tek bir zirve degil.

    Fonksiyon ve testleri DURUYOR cunku olcumun kendisi degerli: bu
    fikir bariz gorunuyor ve tekrar akla gelecek. Yeniden denemeden
    once buraya bakilmali.
    """
    m = DANISTAY_GEREKCE_RE.search(metin or "")
    if not m:
        return metin
    kalan = metin[m.start():].strip()
    # Cok kisa kaldiysa isaret muhtemelen basliktan degil metin icinden
    # gelmistir; tam metne don.
    return kalan if len(kalan) >= 400 else metin


def parcala(metin: str, boyut: int = PARCA_BOYU) -> list[str]:
    """Metni paragraf sinirlarindan boyut'a yakin parcalara boler."""
    parcalar: list[str] = []
    tampon = ""
    for paragraf in metin.split("\n"):
        if len(tampon) + len(paragraf) + 1 > boyut and tampon:
            parcalar.append(tampon.strip())
            tampon = paragraf
        else:
            tampon = f"{tampon}\n{paragraf}" if tampon else paragraf
    if tampon.strip():
        parcalar.append(tampon.strip())
    return [p for p in parcalar if len(p) >= 80]


def parse(kayit: dict, boyut: int = PARCA_BOYU) -> list[Karar]:
    """Indirilmis bir karar kaydini indekslenebilir parcalara cevirir.

    Bos liste doner: karar cok kisaysa ya da kunye disinda icerigi yoksa.
    """
    ham = kayit.get("metin") or ""
    tam = html_metne(ham)
    govde = kunye_at(tam)
    if len(govde) < EN_AZ_METIN:
        return []

    parcalar = parcala(govde, boyut)
    if not parcalar:
        return []

    ortak = dict(
        karar_id=str(kayit.get("id", "")),
        daire=re.sub(r"\s+", " ", kayit.get("daire", "")).strip(),
        esas_no=kayit.get("esas_no", ""),
        karar_no=kayit.get("karar_no", ""),
        karar_tarihi=kayit.get("karar_tarihi", ""),
        durum=kayit.get("durum", ""),
        anahtar=kayit.get("anahtar", ""),
        mahkeme=kayit.get("mahkeme", "Yargıtay"),
        tam_metin=tam,
    )
    return [Karar(**ortak, gerekce=p, parca_no=i, parca_adet=len(parcalar))
            for i, p in enumerate(parcalar, 1)]
