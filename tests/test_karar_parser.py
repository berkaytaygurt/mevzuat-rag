"""Karar ayristiricisi.

Onceki surum gerekceyi "GEREĞİ DÜŞÜNÜLDÜ" isaretiyle buluyordu; indirilen 15
gercek kararda bu ifade HIC gecmiyordu (olculdu) ve kod sessizce "metnin
ikinci yarisi" yedegine dusuyordu. Bu testler o varsayima geri donulmesini
engelliyor.
"""
from scraper.karar_parser import html_metne, kunye_at, parcala, parse

KARAR = {
    "id": "100327600",
    "daire": "9. Hukuk Dairesi",
    "esas_no": "2015/38005",
    "karar_no": "2016/3033",
    "anahtar": "kıdem tazminatı",
    "metin": (
        "<p>9. Hukuk Dairesi 2015/38005 E. , 2016/3033 K.</p>"
        "<p>\"İçtihat Metni\"</p>"
        "<p>Mahkemesi :İş Mahkemesi</p>"
        "<p>Dava Türü : Alacak</p>"
        "<p>TARİHİ : 08/12/2011</p>"
        "<p>NUMARASI : 2011/199-2011/1035</p>"
        "<p>Y A R G I T A Y K A R A R I</p>"
        "<p>Hüküm süresi içinde davalı avukatı tarafından temyiz edilmiş olmakla, "
        "dosya incelendi.</p>"
        "<p>Kıdem tazminatına hak kazanma noktasında en az bir yıllık çalışma "
        "koşulu, İş Kanunu sistemi içinde nispi emredici bir kural olarak kabul "
        "edilmeli ve işçi lehine yorumlanmalıdır. İşçinin işyerinde fiilen "
        "çalışmaya başladığı tarih, bir yıllık sürenin başlangıcıdır.</p>"
    ),
}


def test_kunye_atiliyor():
    govde = kunye_at(html_metne(KARAR["metin"]))
    for atilmali in ("İçtihat Metni", "Mahkemesi", "Dava Türü", "TARİHİ",
                     "NUMARASI", "Y A R G I T A Y", "temyiz edilmiş olmakla"):
        assert atilmali not in govde, f"kunye satiri kaldi: {atilmali}"


def test_govde_korunuyor():
    govde = kunye_at(html_metne(KARAR["metin"]))
    assert "en az bir yıllık çalışma" in govde
    assert "nispi emredici" in govde


def test_isaret_olmadan_da_parca_uretiyor():
    # Bu kararda "GEREĞİ DÜŞÜNÜLDÜ" yok; eski kod burada metnin yarisini atiyordu.
    assert "GEREĞİ DÜŞÜNÜLDÜ" not in KARAR["metin"]
    p = parse(KARAR)
    assert p, "isaret yok diye karar tumuyle kayboldu"
    assert any("bir yıllık sürenin başlangıcıdır" in x.gerekce for x in p)


def test_parca_chunk_id_benzersiz():
    uzun = dict(KARAR, metin=KARAR["metin"] * 6)
    p = parse(uzun)
    assert len(p) > 1, "uzun karar tek parcada birakildi"
    assert len({x.chunk_id for x in p}) == len(p), "chunk_id cakisiyor"
    assert all(x.parca_adet == len(p) for x in p)


def test_kisa_karar_elenir():
    assert parse({"id": "1", "metin": "<p>Mahkemesi :İş Mahkemesi</p>"}) == []


def test_parcalar_boyutu_asmiyor():
    for p in parcala("satir\n" * 900 + "son", boyut=1500):
        assert len(p) <= 1700, f"parca cok uzun: {len(p)}"


def test_kisa_ad_parcayi_gosteriyor():
    p = parse(dict(KARAR, metin=KARAR["metin"] * 6))
    assert "9. Hukuk Dairesi" in p[0].kisa_ad
    assert "(1/" in p[0].kisa_ad
