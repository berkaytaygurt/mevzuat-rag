"""Uzun maddelerin gomme penceresine sigmayan kismi icin cocuk parcalar.

OLCULEN SORUN
Gomme modelinin penceresi 512 token. Maddeleri bilerek bolmuyoruz --
hukuk metni zaten maddelere bolunmus ve sabit karakterle kesmek maddenin
butunlugunu bozuyor. Ama olculdu:

    maddelerin %17,9'u pencereyi asiyor
    tum icerigin %22,8'i vektore hic girmiyor

Yani uzun maddenin sonundaki fikra vektor aramasinda GORUNMUYOR. Izole
edilerek olculdu (40 uzun kanun maddesi, saf vektor aramasi):

    maddenin BASINDAN alinan ifade   1. sirada 25/40, ilk 50'de 36/40
    maddenin SONUNDAN alinan ifade   1. sirada  5/40, ilk 50'de 13/40

BM25 tarafinda bu sorun yok; o maddenin tamamini goruyor. Sistemin
bugune kadar ayakta kalmasinin sebebi bu.

COZUM: PARENT-CHILD, AMA YALNIZCA KUYRUK ICIN
Yaygin "small-to-big" tarifi butun belgeyi cocuklara boler. Bizde buna
gerek yok: maddenin BASI zaten mevcut vektorde kapsaniyor. Yalnizca
PENCEREYE SIGMAYAN kisim icin cocuk uretiliyor. Boylece 275 bin maddeyi
bastan gommek (4 saat) yerine ~55 bin cocuk gomuluyor (~40 dakika) ve
mevcut vektorler gecerli kaliyor.

Arama cocukta yapilir, kullaniciya PARENT maddenin tamami doner.
"""
from __future__ import annotations

import re

import config

# Cocuk parca boyu (token). Pencerenin (512) altinda tutuluyor ki parca
# kendi basina da kesilmeden gomulebilsin.
COCUK_TOKEN = 400
# Ust uste binme: fikra sinirinda kesilen bir hukum iki parcaya bolunurse
# ikisinde de yarim kalmasin diye.
BINDIRME_TOKEN = 60

# Fikra sinirlari: "(1)", "(2)" ... Kanun metni bu isaretlerle bolunuyor
# ve arayuzde de ayni sinirdan paragrafliyoruz.
FIKRA_RE = re.compile(r"(?=\(\d{1,2}\)\s)")


def _bol(metin: str, tokenizer, bas_token: int) -> list[str]:
    """Metnin bas_token'dan SONRASINI parcalara boler.

    Once fikra sinirlarindan denenir; bir fikra tek basina parca boyunu
    asiyorsa token sayisina gore kesilir.
    """
    tokenlar = tokenizer.encode(metin, add_special_tokens=False)
    if len(tokenlar) <= bas_token:
        return []

    # Kuyruk, bindirme kadar geriden basliyor: pencere sinirinda kesilen
    # cumle iki tarafta da yarim kalmasin.
    baslangic = max(0, bas_token - BINDIRME_TOKEN)
    kuyruk = tokenizer.decode(tokenlar[baslangic:])

    # Fikra sinirlarindan topla
    parcalar: list[str] = []
    tampon = ""
    for kesit in FIKRA_RE.split(kuyruk):
        if not kesit.strip():
            continue
        aday = f"{tampon} {kesit}".strip() if tampon else kesit.strip()
        if len(tokenizer.encode(aday, add_special_tokens=False)) > COCUK_TOKEN and tampon:
            parcalar.append(tampon.strip())
            tampon = kesit.strip()
        else:
            tampon = aday
    if tampon.strip():
        parcalar.append(tampon.strip())

    # Fikra siniri yoksa ya da tek fikra cok uzunsa token bazinda kes
    son: list[str] = []
    for p in parcalar:
        t = tokenizer.encode(p, add_special_tokens=False)
        if len(t) <= COCUK_TOKEN:
            son.append(p)
            continue
        adim = COCUK_TOKEN - BINDIRME_TOKEN
        for i in range(0, len(t), adim):
            dilim = tokenizer.decode(t[i:i + COCUK_TOKEN])
            if dilim.strip():
                son.append(dilim.strip())
    return son


def cocuklari_uret(kayitlar: list[dict], tokenizer,
                   embed_metni) -> list[dict]:
    """Pencereyi asan kayitlar icin cocuk parca kayitlari uretir.

    Doner: her biri {"ana_chunk_id", "chunk_id", "cocuk_metin", ...} tasiyan
    kayit listesi. Ana kaydin alanlari kopyalanir; cagiran taraf cocugun
    gomulecek metnini embed_metni({**cocuk, "metin": cocuk_metin}) ile
    kurar.

    BASLIK HER COCUKTA TEKRARLANIR. Yalnizca govde parcasini gommek
    baglami yok ediyor: "(4) Isveren bu sureyi ..." tek basina hangi
    kanunun hangi maddesi oldugunu soylemiyor ve vektor alakasiz
    cikiyor. Bu yuzden bolme, tam metnin degil GOVDENIN uzerinde
    yapiliyor ve baslik uzunlugu pencereden dusuluyor.
    """
    sinir = config.EMBED_MAX_SEQ
    cocuklar: list[dict] = []
    for kayit in kayitlar:
        tam = embed_metni(kayit)
        tokenlar = tokenizer.encode(tam, add_special_tokens=False)
        if len(tokenlar) <= sinir:
            continue
        # Basligin kapladigi yer her cocukta tekrarlanacak; govdeye kalan
        # pencere bu kadar dar.
        baslik_uz = len(tokenizer.encode(embed_metni({**kayit, "metin": ""}),
                                         add_special_tokens=False))
        parcalar = _bol(kayit.get("metin", ""), tokenizer,
                        max(1, sinir - baslik_uz))
        ana = kayit.get("chunk_id", "")
        for i, p in enumerate(parcalar, 1):
            c = dict(kayit)
            c["ana_chunk_id"] = ana
            c["chunk_id"] = f"{ana}#k{i}"
            c["cocuk_metin"] = p
            cocuklar.append(c)
    return cocuklar


COCUK_VEKTOR = "cocuk_vektorler.npy"
COCUK_KAYIT = "cocuk_kayitlar.json"


class CocukDeposu:
    """Cocuk parcalarin vektor deposu.

    AYRI dosyada duruyor: ana indekse dokunmadan kurulabiliyor ve
    bozulursa arama ana vektorlerle calismaya devam ediyor.
    """

    def __init__(self, yol=None):
        import json
        from pathlib import Path

        self.yol = Path(yol) if yol else config.INDEX_DIR
        self._json = json
        self._vek = None
        self._anahtarlar: list[str] | None = None

    def _yukle(self) -> bool:
        if self._vek is not None:
            return True
        import numpy as np

        v = self.yol / COCUK_VEKTOR
        k = self.yol / COCUK_KAYIT
        if not (v.exists() and k.exists()):
            return False
        self._vek = np.load(v)
        # Yalnizca ana chunk_id listesi tutuluyor: cocugun metnine arama
        # sirasinda ihtiyac yok, kullaniciya ana madde donuyor.
        self._anahtarlar = self._json.loads(k.read_text(encoding="utf-8"))
        if len(self._anahtarlar) != len(self._vek):
            self._vek, self._anahtarlar = None, None
            return False
        return True

    def hazir_mi(self) -> bool:
        return self._yukle()

    def sayi(self) -> int:
        return len(self._anahtarlar) if self._yukle() else 0

    def ara(self, vektor, limit: int = 25) -> list[tuple[str, float]]:
        """(ana_chunk_id, skor) listesi; ayni maddeden en iyi cocuk kalir."""
        if not self._yukle():
            return []
        import numpy as np

        skorlar = self._vek @ np.asarray(vektor, dtype=np.float32)
        # Ayni maddeden birden fazla cocuk gelebilir; en iyisi yeter.
        en_iyi: dict[str, float] = {}
        for i in np.argsort(-skorlar)[:limit * 4]:
            ana = self._anahtarlar[int(i)]
            s = float(skorlar[int(i)])
            if s > en_iyi.get(ana, -1.0):
                en_iyi[ana] = s
        return sorted(en_iyi.items(), key=lambda x: x[1], reverse=True)[:limit]
