"""Arama isabetini olcmek icin soru/cevap seti.

Her kayit: (soru, kanun_no, madde_no). Madde numarasi None ise yalnizca dogru
kanunun bulunmasi beklenir.

Bu set elle yazildi ve `dogrula.py` ile kulliyatta gercekten var olduklari
kontrol edildi. Amac kapsamli bir deneme degil, degisikliklerin isabeti
artirip artirmadigini olcebilmek. Gercek bir olcum seti icin hukuk bilen
birinin yazdigi 200+ soru gerekir.
"""
from __future__ import annotations

SORULAR: list[tuple[str, str, str | None]] = [
    # --- Is Kanunu (4857) ---
    ("yillik ucretli izin suresi kac gundur", "4857", "53"),
    ("yıllık izne hak kazanmak için ne kadar çalışmak gerekir", "4857", "53"),
    ("işçinin haklı nedenle derhal fesih hakkı", "4857", "24"),
    ("işverenin haklı nedenle derhal fesih hakkı", "4857", "25"),
    ("ihbar öneli süreleri nedir", "4857", "17"),
    ("fazla çalışma ücreti nasıl hesaplanır", "4857", "41"),
    ("haftalık çalışma süresi kaç saattir", "4857", "63"),
    ("işe iade davası şartları", "4857", "18"),

    # --- Turk Borclar Kanunu (6098) ---
    ("kira bedelinin belirlenmesi", "6098", "344"),
    ("kiracının aile konutunu feshi eşin rızası", "6098", "349"),
    ("haksız fiil sorumluluğu", "6098", "49"),
    ("zamanaşımı süresi haksız fiilde", "6098", "72"),
    ("genel işlem koşulları", "6098", "20"),

    # --- Turk Medeni Kanunu (4721) ---
    ("evlenme yaşı kaç", "4721", "124"),
    ("boşanma sebebi zina", "4721", "161"),
    ("evlilik birliğinin sarsılması boşanma", "4721", "166"),
    ("nişanlılığın bozulmasında maddi tazminat", "4721", "120"),
    ("velayet kime verilir", "4721", None),
    ("mirasçılık belgesi", "4721", "598"),

    # --- Turk Ceza Kanunu (5237) ---
    ("hırsızlık suçunun cezası nedir", "5237", "141"),
    ("kasten öldürmenin cezası", "5237", "81"),
    ("dolandırıcılık suçu", "5237", "157"),
    ("hakaret suçunun cezası", "5237", "125"),
    ("meşru savunma", "5237", "25"),

    # --- KVKK (6698) ---
    ("kişisel verilerin işlenme şartları", "6698", "5"),
    ("veri sorumlusunun aydınlatma yükümlülüğü", "6698", "10"),
    ("ilgili kişinin hakları nelerdir", "6698", "11"),

    # --- HMK (6100) ---
    ("ihtiyati tedbir kararı", "6100", "389"),
    ("dava dilekçesinde bulunması gerekenler", "6100", "119"),

    # --- Diger kanunlar (kanun duzeyinde) ---
    ("trafik kazasında maddi ve manevi tazminat", "2918", None),
    ("tüketicinin ayıplı maldan doğan hakları", "6502", None),
    ("emekli aylığı bağlanma şartları", "5510", None),
    ("anonim şirket kuruluşu", "6102", None),
    ("icra takibine itiraz süresi", "2004", None),
]
