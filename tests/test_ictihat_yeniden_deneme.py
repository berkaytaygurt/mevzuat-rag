"""Yargitay aramasinin gecici hataya dayanikliligini denetler.

NEDEN VAR
8 hukuk alani icin 55 anahtarlik cekimde, biten 49 anahtarin 16'si
(%33) hic karar getirmedi. Log tek satir soyluyordu:

    WARNING arama 4 denemede sonuc vermedi: manevi tazminat s.1

Ucu elle yeniden denendi ve UCU DE ANINDA sonuc verdi (1.166.584 /
388.237 / 485.205 kayit). Yani anahtarda ya da govdede sorun yok;
sunucu o an "ADALET_RUNTIME_EXCEPTION" doneuyor. Dogrusal bekleme ile
dort deneme ~15 saniyede tukeniyordu ve o anahtarin 60 karari tumden
kayboluyordu -- sessizce, cunku akis hatayi yutup devam ediyor.
"""
import time

from scraper.ictihat import EmsalClient


class _SahteCevap:
    def __init__(self, govde):
        self._govde = govde

    def raise_for_status(self):
        pass

    def json(self):
        return self._govde


class _SahteOturum:
    """Ilk N cagride hata, sonra sonuc doner."""

    def __init__(self, hata_sayisi):
        self.hata_sayisi = hata_sayisi
        self.cagri = 0

    def post(self, url, json=None, timeout=None):
        self.cagri += 1
        if self.cagri <= self.hata_sayisi:
            # Sunucunun gercek davranisi: 200 doner ama data dict degil.
            return _SahteCevap({"data": None})
        return _SahteCevap({"data": {"recordsTotal": 5, "data": []}})


def _istemci(oturum, monkeypatch):
    c = EmsalClient(delay=0.0)
    c.session = oturum
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return c


def test_gecici_hatadan_sonra_sonuc_aliniyor(monkeypatch):
    """Bes ard arda hata eski kodda anahtari bos birakiyordu."""
    oturum = _SahteOturum(hata_sayisi=5)
    c = _istemci(oturum, monkeypatch)
    veri = c._istek_dene("http://x", {}, "deneme")
    assert veri is not None, "gecici hata anahtari bos birakti"
    assert veri["recordsTotal"] == 5


def test_deneme_sayisi_dortten_fazla():
    """Dort deneme olculdu: anahtarlarin ucte biri bos donuyordu."""
    import inspect

    imza = inspect.signature(EmsalClient._istek_dene)
    assert imza.parameters["deneme"].default >= 7


def test_bekleme_ustel_ve_ust_sinirli(monkeypatch):
    """Dogrusal artis (2,5/5/7,5) sitenin toparlanmasina yetmiyordu."""
    beklemeler = []
    monkeypatch.setattr(time, "sleep", beklemeler.append)
    c = EmsalClient(delay=2.5)
    c.session = _SahteOturum(hata_sayisi=99)
    c._bekle = lambda: None
    c._istek_dene("http://x", {}, "deneme")

    assert len(beklemeler) == 6, "denemeler arasi bekleme sayisi degisti"
    # Ustel: her adim oncekinin iki kati -- ta ki tavana carpana kadar.
    assert beklemeler[:4] == [2.5, 5.0, 10.0, 20.0]
    # Ust sinir: sonsuza kadar buyumesin, cekim tikanmasin.
    assert all(b <= 30.0 for b in beklemeler)
    assert sum(beklemeler) > 60, "toplam bekleme hala cok kisa"


def test_tumden_basarisizlikta_none_donuyor(monkeypatch):
    """Vazgecmek de bir davranis: cagiran taraf bunu ayirt edebilmeli."""
    c = _istemci(_SahteOturum(hata_sayisi=99), monkeypatch)
    assert c._istek_dene("http://x", {}, "deneme") is None


# --------------------------------------------------------------------
# Belge indirme: 429 (hiz siniri)
# --------------------------------------------------------------------
class _SahteBelgeCevap:
    def __init__(self, kod, govde=None):
        self.status_code = kod
        self._govde = govde or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Client Error")

    def json(self):
        return self._govde


class _SahteBelgeOturum:
    def __init__(self, kod_dizisi):
        self.kodlar = list(kod_dizisi)
        self.cagri = 0

    def get(self, url, params=None, timeout=None):
        kod = self.kodlar[min(self.cagri, len(self.kodlar) - 1)]
        self.cagri += 1
        if kod == 200:
            return _SahteBelgeCevap(200, {"data": "<p>karar metni burada</p>"})
        return _SahteBelgeCevap(kod)


def _belge_istemci(oturum, tmp_path, monkeypatch):
    c = EmsalClient(delay=1.0, cache_dir=tmp_path)
    c.session = oturum
    c._bekle = lambda: None
    return c


def test_hiz_sinirindan_sonra_belge_geliyor(tmp_path, monkeypatch):
    """Dort 429'dan sonra gelen belge eski kodda kaybediliyordu.

    Olculdu: 55 anahtarlik cekimde 1.253 belge (indirilenlerin ~%17'si)
    boyle dustu. Belgeler duruyordu; elle istendiginde geliyordu.
    """
    beklemeler = []
    monkeypatch.setattr(time, "sleep", beklemeler.append)
    c = _belge_istemci(_SahteBelgeOturum([429, 429, 429, 429, 200]),
                       tmp_path, monkeypatch)
    metin = c.belge("123")
    assert "karar metni" in metin, "429 sonrasi belge hala kayboluyor"


def test_429_normal_hatadan_uzun_bekliyor(tmp_path, monkeypatch):
    """429 "istek bozuk" degil "yavasla" demek; ayri ele alinmali."""
    hiz = []
    monkeypatch.setattr(time, "sleep", hiz.append)
    c = _belge_istemci(_SahteBelgeOturum([429]), tmp_path, monkeypatch)
    c.belge("123")

    ag = []
    monkeypatch.setattr(time, "sleep", ag.append)
    c2 = _belge_istemci(_SahteBelgeOturum([500]), tmp_path, monkeypatch)
    c2.belge("456")

    assert sum(hiz) > sum(ag), "429 normal hatadan uzun beklemiyor"
    assert sum(hiz) >= 180, "hiz siniri penceresi icin cok kisa"


def test_basarili_belge_onbellege_yaziliyor(tmp_path, monkeypatch):
    """Onbellek olmadan kopan cekim bastan basliyor."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    oturum = _SahteBelgeOturum([200])
    c = _belge_istemci(oturum, tmp_path, monkeypatch)
    c.belge("789")
    once = oturum.cagri
    c.belge("789")
    assert oturum.cagri == once, "onbellek kullanilmiyor"


def test_bos_belge_onbellege_yazilmiyor(tmp_path, monkeypatch):
    """Basarisizligi onbelleklemek hatayi kalicilastirir."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    c = _belge_istemci(_SahteBelgeOturum([429]), tmp_path, monkeypatch)
    assert c.belge("999") == ""
    assert not c._cache_yolu("999").exists(), "bos sonuc onbelleklendi"
