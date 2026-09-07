"""Canli Yargitay karar cekiminin denetimi.

NEDEN VAR
Kararlar bugune kadar elle yazilmis 55 anahtar kelimeyle onceden
indiriliyordu. Listede olmayan konu sorulunca karar bolumu bos
geliyordu -- Yargitay'da o konuda yuz binlerce karar dururken.

Canli cekim bunu kaldiriyor ama iki tuzagi var, ikisi de burada
denetleniyor:

  1. Yargitay'in aramasi ANLAM BILMIYOR. Dogal cumle verilirse
     kelimeleri OR'layip alakasiz karar getiriyor. Olculdu:
       soru  "babam olmeden once tapuyu kardesime devretmis..."
       donen "kadastro oncesi nedene dayali tapu iptali"  (yanlis)
       terim "muris muvazaasi" -> dogru kararlar
     Yani terime cevirme adimi ATLANAMAZ.

  2. Ag hatasi CEVABI ENGELLEMEMELI. Canli cekim bir ek; Yargitay
     kapaliysa sistem yerel kulliyatla calismaya devam etmeli.
"""
import json

import pytest

from core.canli_karar import CanliKararArayici, arama_terimi


class _SahteUretici:
    def __init__(self, cevap="muris muvazaası", patla=False):
        self.cevap = cevap
        self.patla = patla
        self.cagrilar = []

    def _gemini(self, istem, sistem=None, model=None):
        self.cagrilar.append(istem)
        if self.patla:
            raise RuntimeError("gemini yok")
        return self.cevap


class _SahteKayit:
    def __init__(self, i):
        self.id = str(i)
        self.daire = "1. Hukuk Dairesi"
        self.esas_no = f"2020/{i}"
        self.karar_no = f"2021/{i}"
        self.karar_tarihi = "01.01.2021"


class _SahteIstemci:
    def __init__(self, adet=5, arama_patlar=False, bos_belge=()):
        self.adet = adet
        self.arama_patlar = arama_patlar
        self.bos_belge = set(bos_belge)
        self.aranan = []

    def ara(self, kelime, en_fazla=10, sayfa_boyu=10):
        self.aranan.append(kelime)
        if self.arama_patlar:
            raise RuntimeError("ag yok")
        return [_SahteKayit(i) for i in range(min(self.adet, en_fazla))]

    def belge(self, kid):
        if kid in self.bos_belge:
            return ""
        return f"karar metni {kid}"


@pytest.fixture(autouse=True)
def _birikimi_izole_et(tmp_path, monkeypatch):
    """Testler gercek birikim dosyasina yazmasin."""
    import core.canli_karar as ck
    monkeypatch.setattr(ck, "CANLI_BIRIKIM", tmp_path / "canli.json")


# ---------- terim cikarma ----------

def test_dogal_cumle_hukuki_terime_cevriliyor():
    u = _SahteUretici("muris muvazaası")
    assert arama_terimi("babam tapuyu kardeşime devretmiş", u) == "muris muvazaası"


def test_hukuki_olmayan_soruda_terim_uretilmiyor():
    """HyDE'de ogrenildi: cikis yolu olmazsa model her soruyu zorluyor."""
    assert arama_terimi("kahve nasıl demlenir", _SahteUretici("YOK")) == ""


def test_tirnak_temizleniyor():
    u = _SahteUretici('"ecrimisil"')
    assert arama_terimi("işgal bedeli isteyebilir miyim", u) == "ecrimisil"


def test_uretici_patlarsa_bos_donuyor():
    """Gemini erisilemezse canli cekim sessizce devre disi kalmali."""
    assert arama_terimi("bir soru", _SahteUretici(patla=True)) == ""


def test_asiri_uzun_terim_kirpiliyor():
    """Kelime yigini Yargitay aramasinda OR'lanip gurultu getiriyor."""
    u = _SahteUretici("kelime " * 40)
    assert len(arama_terimi("soru", u)) <= 60


# ---------- canli arama ----------

def test_terim_uretilemezse_aga_cikilmiyor():
    """Bosuna ag istegi hem yavas hem 429 riski."""
    ist = _SahteIstemci()
    c = CanliKararArayici(_SahteUretici("YOK"), istemci=ist)
    assert c.ara("kahve nasıl demlenir") == []
    assert ist.aranan == [], "terim yokken aga cikildi"


def test_arama_dogal_cumleyle_degil_terimle_yapiliyor():
    """Tasarimin can alici noktasi: Yargitay'a TERIM gidiyor."""
    ist = _SahteIstemci()
    c = CanliKararArayici(_SahteUretici("muris muvazaası"), istemci=ist)
    c.ara("babam ölmeden önce tapuyu kardeşime devretmiş, pay alır mıyım")
    assert ist.aranan == ["muris muvazaası"], "ham cumle gonderilmis"


def test_ag_hatasi_cevabi_engellemiyor():
    """Yargitay kapaliysa sistem yerel kulliyatla devam etmeli."""
    c = CanliKararArayici(_SahteUretici(), istemci=_SahteIstemci(arama_patlar=True))
    assert c.ara("bir soru") == []


def test_bos_belgeler_eleniyor():
    ist = _SahteIstemci(adet=5, bos_belge={"0", "1", "2"})
    c = CanliKararArayici(_SahteUretici(), istemci=ist)
    r = c.ara("bir soru", limit=5)
    assert len(r) == 2
    assert all(x["metin"] for x in r)


def test_reranker_soruya_gore_siraliyor():
    """Yargitay'in kendi siralamasi tarihe gore; soruyla ilgisi yok.

    Deger kattigimiz yer burasi -- yoksa avukatin kendi sitede
    yapacagindan farki kalmaz.
    """
    class _Ters:
        def sirala(self, soru, adaylar, limit=None):
            return list(reversed(adaylar))

    ist = _SahteIstemci(adet=4)
    c = CanliKararArayici(_SahteUretici(), reranker=_Ters(), istemci=ist)
    r = c.ara("bir soru", limit=4)
    assert r[0]["karar_id"] == "3", "yeniden siralama uygulanmamis"


def test_reranker_patlarsa_ham_sira_kullaniliyor():
    class _Patlak:
        def sirala(self, *a, **k):
            raise RuntimeError("model yok")

    c = CanliKararArayici(_SahteUretici(), reranker=_Patlak(),
                          istemci=_SahteIstemci(adet=3))
    assert len(c.ara("bir soru", limit=3)) == 3


# ---------- birikim ----------

def test_gelen_kararlar_birikime_yaziliyor(tmp_path):
    """Kulliyat gercek sorulardan buyuyor; birikim bunun deposu."""
    import core.canli_karar as ck
    c = CanliKararArayici(_SahteUretici(), istemci=_SahteIstemci(adet=3))
    c.ara("bir soru", limit=1)
    kayit = json.loads(ck.CANLI_BIRIKIM.read_text(encoding="utf-8"))
    # limit 1 olsa da CEKILEN her karar birikiyor: bir dahaki sefere
    # ag istegi yapilmasin.
    assert len(kayit) == 3


def test_ayni_karar_iki_kez_birikmiyor():
    import core.canli_karar as ck
    c = CanliKararArayici(_SahteUretici(), istemci=_SahteIstemci(adet=3))
    c.ara("bir soru")
    c.ara("baska soru")
    assert len(json.loads(ck.CANLI_BIRIKIM.read_text(encoding="utf-8"))) == 3


def test_birikim_yazilamazsa_cevap_yine_geliyor(monkeypatch):
    """Birikim bir kolaylik; sistemin calismasi buna bagli degil."""
    import core.canli_karar as ck
    monkeypatch.setattr(ck, "CANLI_BIRIKIM", "\x00gecersiz/yol.json")
    c = CanliKararArayici(_SahteUretici(), istemci=_SahteIstemci(adet=2))
    assert len(c.ara("bir soru", limit=2)) == 2


# --------------------------------------------------------------------
# Istem kalitesi: model terim UYDURMAMALI
# --------------------------------------------------------------------
def test_istem_terim_uydurmayi_yasakliyor():
    """Model olmayan dava adlari uretiyordu; kural metinde durmali.

    OLCULDU: "patent hakkina tecavuz halinde ne talep edilebilir"
    sorusuna bir kez "patent hakkina tecavuz tazminati" (dogru), bir kez
    "patent infisahi tazminat" uretildi. Boyle bir dava yok -- infisah
    sona erme demek, tecavuzle ilgisi yok. Sicaklik 0 olmasina ragmen
    ayni girdi farkli cikti verebiliyor.

    Yanlis terim SESSIZCE yanlis kararlar getiriyor: hata mesaji yok,
    yalnizca alakasiz sonuc. Marka sorusunda da boyle oldu -- soru
    TECAVUZ iken terim "markanin hukumsuzlugu davasi" uretildi ve
    kararlarin alaka puani 0,117 / 0,026 / 0,024'e dustu.
    """
    from core.canli_karar import SISTEM

    assert "UYDURMA" in SISTEM.upper(), "terim uydurma yasagi kayip"
    assert "YERLEŞİK" in SISTEM.upper(), "yerlesik terim kurali kayip"


def test_istem_ornek_iceriyor():
    """Ornek olmadan model teknik adi bulamiyordu."""
    from core.canli_karar import SISTEM

    assert SISTEM.count("Olay:") >= 5, "yeterli ornek yok"
    assert "muris muvazaası" in SISTEM
    # Hukuki olmayan soru ornegi de sart: cikis yolu ogretilmeli.
    assert "YOK" in SISTEM


def test_istem_uzunluk_sinirini_soyluyor():
    """Kelime yigini Yargitay aramasinda OR'lanip gurultu getiriyor."""
    from core.canli_karar import SISTEM

    assert "4 kelime" in SISTEM
