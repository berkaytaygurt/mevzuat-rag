"""Yeniden siralayicinin KARAR metnini gerceketen gordugunu denetler.

NEDEN VAR
Mahkeme kararlari ile kanun maddeleri FARKLI alan adlari kullaniyor:

    madde kaydi   mevzuat_adi / madde_no / baslik / metin
    karar kaydi   kisa_ad / daire / esas_no / GEREKCE / tam_metin

_madde_metni() yalnizca madde alanlarina bakiyordu. Karar kayitlarinda
bu alanlarin dordu de bos oldugu icin cross-encoder'a giden metin
neredeyse BOS kaliyordu ("Madde " dizgisi). Yani karar tarafinda yeniden
siralama HIC calismiyordu; sonuc RRF'in %10'luk payina kaliyordu.

OLCULDU (ham cross-encoder puani, 6 soru, duzeltmeden ONCE):
    0,000  0,000  0,000  0,000  0,000  0,006

Duzeltmeden SONRA "isci kidem tazminatini hangi hallerde alamaz"
sorusu 9. Hukuk Dairesi'ni 0,949 ile getiriyor -- once 0,000 idi ve
yanlis daireler geliyordu.

Belirti sinsi: sistem calisiyor, karar donuyor, hata mesaji yok --
yalnizca donen kararlar konuyla ilgisiz.
"""
from core.reranker import Reranker


def test_karar_govdesi_gerekce_alanindan_okunuyor():
    karar = {
        "kisa_ad": "Yargıtay 9. Hukuk Dairesi 2020/1 E.",
        "daire": "9. Hukuk Dairesi",
        "gerekce": "Kıdem tazminatına hak kazanma koşulları bakımından...",
    }
    metin = Reranker._madde_metni(karar)
    assert "Kıdem tazminatına hak kazanma" in metin, "karar govdesi kayip"
    assert "9. Hukuk Dairesi" in metin, "karar kimligi kayip"


def test_gerekce_yoksa_tam_metne_dusuyor():
    karar = {"kisa_ad": "Yargıtay 1. HD", "tam_metin": "Muris muvazaası nedeniyle"}
    assert "Muris muvazaası" in Reranker._madde_metni(karar)


def test_madde_kaydi_eskisi_gibi_calisiyor():
    """Duzeltme madde tarafini BOZMAMALI -- olculen isabet oradan geliyor."""
    madde = {
        "mevzuat_adi": "İŞ KANUNU",
        "madde_no": "25",
        "baslik": "İşverenin haklı nedenle derhal fesih hakkı",
        "metin": "Süresi belirli olsun veya olmasın işveren...",
    }
    m = Reranker._madde_metni(madde)
    assert m.startswith("İŞ KANUNU")
    assert "Madde 25" in m
    assert "haklı nedenle derhal fesih" in m
    assert "Süresi belirli olsun" in m


def test_madde_no_yoksa_bos_madde_etiketi_uretilmiyor():
    """Eski kod madde_no bos olsa da "Madde " dizgisini ekliyordu.

    Tek basina zararsiz gorunuyor ama kararlarda govde de bos oldugu
    icin cross-encoder'a giden metnin TAMAMI buydu.
    """
    assert "Madde" not in Reranker._madde_metni({"gerekce": "bir karar metni"})


def test_bos_kayit_cokmuyor():
    assert Reranker._madde_metni({}) == ""


def test_karar_metni_bos_donmuyor():
    """Asil regresyon: karar kaydi verildiginde metin BOS OLMAMALI."""
    karar = {"karar_id": "1", "gerekce": "x" * 200, "chunk_id": "karar-1"}
    assert len(Reranker._madde_metni(karar)) >= 200
