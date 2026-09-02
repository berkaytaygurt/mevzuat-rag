"""Madde basligi olmayan belgeler ve PDF adres kalibi.

Bu iki hata birlikte kataloğun %28'ini (4.099 belge) indeksin disinda
birakmisti; ikisi de sessiz kaybediyordu, hata vermiyordu.
"""
from scraper.client import MevzuatClient
from scraper.parser import maddeleri_cikar

DUZ_METIN = [
    "EMLAK VERGISI KANUNU GENEL TEBLIGI",
    "(SERI NO: 90)",
    "29/7/1970 tarihli ve 1319 sayili Emlak Vergisi Kanununun 29 uncu maddesinin "
    "birinci fikrasinin (b) bendinde, binalar icin vergi degerinin Bakanlikca "
    "musterek tespit ve ilan edilecek bina metrekare normal insaat maliyetleri "
    "ile bulunacak arsa payi degeri esas alinarak hesaplanacagi belirtilmistir.",
    "Bu Teblig ekinde yer alan cetvel, 2026 yili icin uygulanacaktir.",
]


def test_madde_yoksa_belge_kaybolmuyor():
    m = maddeleri_cikar(DUZ_METIN, tur_adi="Teblig", mevzuat_no="46237", tertip="5")
    assert m, "madde basligi olmayan belge tumuyle atildi"
    assert all(x.metin.strip() for x in m)
    assert all(x.madde_no.startswith("Metin") for x in m)


def test_duz_metin_parcalari_benzersiz():
    m = maddeleri_cikar(DUZ_METIN * 12, tur_adi="Teblig", mevzuat_no="1", tertip="5")
    assert len(m) > 1, "uzun belge tek parcada birakildi"
    assert len({x.chunk_id for x in m}) == len(m), "chunk_id cakismasi"


def test_kisa_metin_parcalanmiyor():
    assert maddeleri_cikar(["Kisa not."], tur_adi="Teblig",
                           mevzuat_no="1", tertip="5") == []


def test_maddeli_belge_duz_metne_dusmuyor():
    bloklar = ["ORNEK YONETMELIK", "Amac", "MADDE 1 - (1) Bu Yonetmeligin amaci "
               "ornek olusturmaktir ve yeterince uzun bir metin icermektedir."]
    m = maddeleri_cikar(bloklar, tur_adi="Yonetmelik", mevzuat_no="1", tertip="5")
    assert m and not m[0].madde_no.startswith("Metin")


def test_teblig_pdf_dizini_yonetmelik():
    # Teblig/kurum yonetmeligi PDF'leri /MevzuatMetin/yonetmelik/ altinda;
    # alt dizinsiz adres bos PDF donduruyordu.
    assert MevzuatClient.PDF_DIZINLERI[9] == "yonetmelik/"
    assert MevzuatClient.PDF_DIZINLERI[8] == "yonetmelik/"
    assert MevzuatClient.PDF_DIZINLERI.get(1, "") == ""


def test_bos_pdf_boyutu_taniniyor():
    assert MevzuatClient.BOS_PDF_BOYUTU == 60487


def test_bakim_sayfasi_indekse_girmiyor():
    # Sunucunun bakim sayfasi 10.832 karakter metin tasiyor; duz metin yedegi
    # bunu gercek belge sanip 68 cop kayit indekslemisti.
    from scraper.parser import maddeleri_cikar
    bakim = ["T.C. CUMHURBAŞKANLIĞI", "Sayfada Çalışma Yapılmaktadır",
             "DTSt226GL2xN1xxx2bnnjicYcIW1HsAHDT2Pj45jNnzvR08Sn12aEKsAHeKx" * 40]
    assert maddeleri_cikar(bakim, tur_adi="Teblig", mevzuat_no="1", tertip="5") == []


def test_sahte_pdf_boyutlari():
    from scraper.client import MevzuatClient
    for boyut in (60487, 64854, 259488):
        assert boyut in MevzuatClient.SAHTE_PDF_BOYUTLARI


def test_bos_pdf_baytinda_hata_atmiyor():
    # Istemci sahte PDF'lerde b"" donduruyor. parse_pdf burada istisna
    # atarsa cagiran taraftaki HTML yedegi hic denenmiyor ve belge
    # gereksiz yere kayboluyor.
    from scraper.parser import parse_pdf
    assert parse_pdf(b"", tur_adi="Teblig", mevzuat_no="1", tertip="5") == []


def test_guvenli_yaz_atomik(tmp_path):
    """Yazma yarida kesilse bile eski dosya bozulmamali.

    Dogrudan write_text kullanildiginda 358 MB'lik kulliyat dosyasi bir kez
    sifirlandi ve 275.806 madde yedekten geri getirilmek zorunda kalindi.
    """
    import json
    import cli

    yol = tmp_path / "veri.json"
    cli.guvenli_yaz(yol, [{"a": 1}])
    assert json.loads(yol.read_text(encoding="utf-8")) == [{"a": 1}]

    # Yeniden yazim eskisini bozmadan degistirmeli
    cli.guvenli_yaz(yol, [{"a": 2}, {"b": 3}])
    assert len(json.loads(yol.read_text(encoding="utf-8"))) == 2
    # Gecici dosya arkada birakilmamali
    assert not list(tmp_path.glob("*.tmp"))
