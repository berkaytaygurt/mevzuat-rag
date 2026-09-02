"""Sayfa alti dipnotunun madde metnini kesmedigini denetler.

NEDEN VAR
4857 sayili Is Kanunu m.19 kulliyata 112 karakter olarak girmisti. Maddenin
"Hakkindaki iddialara karsi savunmasini almadan ... feshedilemez" fikrasi --
ise iade davalarinin dayandigi hukum -- kulliyatta HIC YOKTU.

Sebep: PDF'te sayfa alti dipnotu maddenin iki fikrasi ARASINA dusuyor.
Ayristirici dipnotu gorunce flush() cagirip maddeyi kapatiyor, sonraki
fikralar current=None oldugu icin sessizce cope gidiyordu.

Bu tek bir maddenin sorunu degildi: kulliyattaki 4.330 mulga olmayan madde
120 karakterin altindaydi.
"""
from scraper.parser import maddeleri_cikar

# 4857 m.19'un PDF'ten cikan gercek satir dizilimi (dipnot ortada)
BLOKLAR = [
    "İŞ KANUNU",
    "Kanun Numarası : 4857",
    "Sözleşmenin feshinde usul",
    "Madde 19 - İşveren fesih bildirimini yazılı olarak yapmak ve fesih sebebini açık ve",
    "kesin bir şekilde belirtmek zorundadır.",
    "6 18/2/2009 tarihli ve 5838 sayılı Kanunun 32 nci maddesiyle; bu bentte yer alan “Mevzuattan veya",
    "sözleşmeden doğan haklarını takip” ibaresinden sonra gelmek üzere “veya yükümlülüklerini yerine",
    "getirmek” ibaresi eklenmiştir.",
    "Hakkındaki iddialara karşı savunmasını almadan bir işçinin belirsiz süreli iş",
    "sözleşmesi, o işçinin davranışı veya verimi ile ilgili nedenlerle feshedilemez.",
    "Fesih bildirimine itiraz ve usulü",
    "Madde 20 - İş sözleşmesi feshedilen işçi, fesih bildiriminde sebep gösterilmediği",
    "iddiası ile bir ay içinde iş mahkemesinde dava açabilir.",
]


def _maddeler():
    return {m.madde_no: m for m in maddeleri_cikar(BLOKLAR, mevzuat_no="4857")}


def test_dipnottan_sonraki_fikra_kaybolmuyor():
    m19 = _maddeler()["19"]
    assert "savunmasını almadan" in m19.metin, f"fikra kayip: {m19.metin!r}"
    assert "feshedilemez" in m19.metin


def test_dipnot_metni_govdeye_sizmiyor():
    m19 = _maddeler()["19"]
    assert "5838" not in m19.metin, f"dipnot sizdi: {m19.metin!r}"
    assert "eklenmiştir" not in m19.metin


def test_sonraki_maddenin_basligi_govdeye_sizmiyor():
    """Baslik satiri hem onceki maddenin govdesine hem de baslik olarak
    giriyordu; her madde bir sonrakinin basligiyla bitiyordu."""
    m = _maddeler()
    assert "Fesih bildirimine itiraz" not in m["19"].metin
    assert m["20"].baslik == "Fesih bildirimine itiraz ve usulü"


def test_sonraki_madde_saglam():
    m20 = _maddeler()["20"]
    assert "bir ay içinde iş mahkemesinde dava açabilir" in m20.metin


# 6518 m.101: govdenin gercek son satiri baslik goruntusu veriyor. Baslik
# temizligi korumasizken bu satir siliniyor ve madde yarim kaliyordu.
BLOKLAR_YANLIS_BASLIK = [
    "KANUN",
    "Kanun Numarası : 6518",
    "Madde 101 - (28/2/2008 tarihli ve 5746 sayılı Araştırma ve Geliştirme",
    "Faaliyetlerinin Desteklenmesi Hakkında Kanun ile ilgili olup yerine işlenmiştir.)",
    "Madde 102 - (14/7/1965 tarihli ve 657 sayılı Devlet Memurları Kanunu ile",
    "ilgili olup yerine işlenmiştir.)",
]


def test_govde_son_satiri_baslik_sanilip_silinmiyor():
    m = {x.madde_no: x for x in maddeleri_cikar(BLOKLAR_YANLIS_BASLIK,
                                                mevzuat_no="6518")}
    assert "yerine işlenmiştir" in m["101"].metin, f"satir silindi: {m['101'].metin!r}"
    assert "Desteklenmesi Hakkında Kanun" in m["101"].metin


# "Madde 3/A" ayri bir hukumdur ve avukat onu "2576 m.3/A" diye anar.
# Harf yakalanmazken hepsi "3" numarasina dusuyor, cakisma da "3 (2)" diye
# cozuluyordu; kimse o adi arayamaz. Olculdu: 1.740 madde bu durumdaydi.
BLOKLAR_HARFLI = [
    "BÖLGE İDARE MAHKEMELERİ KANUNU",
    "Kanun Numarası : 2576",
    "Madde 3 - Bölge idare mahkemeleri, bölge idare mahkemesi başkanı ile iki üyeden oluşur.",
    "Madde 3/A- (Ek: 18/6/2014-6545/4 md.) Bölge idare mahkemelerinin görevleri şunlardır.",
    "Mükerrer Madde 20/D-Türkiye’de yerleşmiş sayılan gerçek kişilerin kazançları.",
]


def test_harf_ekli_madde_numarasi_yakalaniyor():
    m = {x.madde_no: x for x in maddeleri_cikar(BLOKLAR_HARFLI, mevzuat_no="2576")}
    assert "3/A" in m, f"harfli madde yok: {sorted(m)}"
    assert "Mükerrer 20/D" in m, f"mukerrer harfli madde yok: {sorted(m)}"
    # Harf govdede kalmamali
    assert not m["3/A"].metin.startswith("/A")
    assert m["3/A"].metin.startswith("(Ek: 18/6/2014")
    # Duz madde bozulmamali
    assert "3" in m and "iki üyeden oluşur" in m["3"].metin


def test_harfli_madde_chunk_id_cakismiyor():
    m = {x.madde_no: x for x in maddeleri_cikar(BLOKLAR_HARFLI, mevzuat_no="2576")}
    assert m["3"].chunk_id != m["3/A"].chunk_id
