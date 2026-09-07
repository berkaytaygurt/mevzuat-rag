"""Yerel ve canli karar havuzlarinin birlestirilmesini denetler.

NEDEN VAR
Onceki kod iki havuzdan BIRINI seciyordu: en yuksek ce_skor hangisinde
ise o gosteriliyordu. Olculdu, bu yanlis:

    "kiraci iki hakli ihtar nedeniyle tahliye edilebilir mi"
        yerel  8 kararin 8'i de  ce = 0,999
        canli  8 kararin 6'si    ce = 0,999

Puanlar TAVANA VURUYOR. Tavana vurmus iki sayiyi karsilastirmak
yazi-tura demek; ustelik secim yapmak kaybeden havuzdaki alakali
kararlari atiyor.

Ikinci sikayet tarihti: gosterilen kararlar 2009 ve 2014'tu. Alaka
esitken YENI karar daha degerli.
"""
import server


def _k(ad, ce, tarih, canli=False):
    return {"kisa_ad": ad, "ce_skor": ce, "karar_tarihi": tarih, "canli": canli}


def test_iki_havuz_birlestiriliyor():
    yerel = [_k("A", 0.999, "03.07.2014")]
    canli = [_k("B", 0.999, "01.02.2020", canli=True)]
    sonuc, kaynak = server._kararlari_birlestir(yerel, canli)
    adlar = [x["kisa_ad"] for x in sonuc]
    assert adlar == ["B", "A"], "birlestirme ya da tarih siralamasi yanlis"
    assert kaynak == "karma"


def test_alaka_esitken_yeni_tarih_uste():
    """Kullanicinin sikayeti: 'bula bula 2009 mu bulmus'."""
    havuz = [_k("eski", 0.999, "23.11.2009"), _k("yeni", 0.999, "31.10.2016"),
             _k("orta", 0.999, "03.07.2014")]
    sonuc, _ = server._kararlari_birlestir(havuz, [])
    assert [x["kisa_ad"] for x in sonuc] == ["yeni", "orta", "eski"]


def test_alaka_tarihten_once_gelir():
    """Tarih IKINCIL olcut: belirgin sekilde daha alakali olan ustte."""
    havuz = [_k("eski_ama_alakali", 0.95, "01.01.2005"),
             _k("yeni_ama_alakasiz", 0.40, "01.01.2024")]
    sonuc, _ = server._kararlari_birlestir(havuz, [])
    assert sonuc[0]["kisa_ad"] == "eski_ama_alakali"


def test_ayni_karar_iki_havuzda_varsa_tekilleniyor():
    ayni = "Yargıtay 6. HD 2014/6168 E. 2014/8887 K."
    sonuc, _ = server._kararlari_birlestir(
        [_k(ayni, 0.999, "03.07.2014")],
        [_k(ayni, 0.999, "03.07.2014", canli=True)])
    assert len(sonuc) == 1


def test_kisa_ad_yoksa_esas_karar_no_ile_tekilleniyor():
    a = {"esas_no": "2014/1", "karar_no": "2014/2", "ce_skor": 0.9,
         "karar_tarihi": "01.01.2014"}
    b = dict(a, canli=True)
    sonuc, _ = server._kararlari_birlestir([a], [b])
    assert len(sonuc) == 1


def test_tarihsiz_karar_cokmuyor():
    havuz = [_k("tarihsiz", 0.9, ""), _k("bozuk", 0.9, "abc"),
             _k("normal", 0.9, "01.01.2020")]
    sonuc, _ = server._kararlari_birlestir(havuz, [])
    assert len(sonuc) == 3
    assert sonuc[0]["kisa_ad"] == "normal"


def test_kaynak_etiketi_dogru():
    assert server._kararlari_birlestir([_k("A", 0.9, "")], [])[1] == "yerel"
    assert server._kararlari_birlestir([], [_k("B", 0.9, "", canli=True)])[1] == "canli"
    assert server._kararlari_birlestir([], [])[1] == "yerel"


def test_daha_fazla_karar_ucu_var():
    """Uc karar emsal aramak icin yeterli degil; cozum daha COK karar
    cekmek degil, ISTEGE BAGLI cekmek.

    Once varsayilan 6'ya cikarilmisti. Ama canli cekim her soruya 10-30
    saniye ekliyordu ve site Cloudflare tuneli arkasinda: tunelin origin
    zaman asimi 100 saniye, asilinca istek "524" ile tumden dusuyor ve
    avukat cevabin TAMAMINI kaybediyor. Olculdu, cevaplar 90 saniye-2
    dakikaya cikmisti.

    Bu yuzden ilk cevap yerelden ve hizli; daha fazlasi dugmeyle ayri
    bir uctan (/api/kararlar) geliyor.
    """
    yollar = {r.path for r in server.app.routes if hasattr(r, "path")}
    assert "/api/kararlar" in yollar, "daha fazla karar ucu kayip"


def test_canli_cekim_ilk_istekte_kosullu():
    """Canliya yalnizca yerel zayifken cikilmali."""
    import inspect

    kaynak = inspect.getsource(server._en_iyi_kararlar)
    assert "len(yerel_sonuc) < CANLI_YEDEK_SINIRI" in kaynak, (
        "canli cekim kosulsuz calisiyor; her soruya 10-30 sn ekler")
