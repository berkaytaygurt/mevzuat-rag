"""Devam sorusu olcum seti: baglam kurmanin isabete etkisi.

NEDEN IKI AYRI SET

Sohbet artik bir akis; kullanici ikinci soruyu "peki bu sure ne kadar"
diye soruyor. Sistem su an geemisi hic gormuyor, her soru sifirdan
araniyor. Baglam eklemek istiyoruz -- ama baglam ISE YARADIGI KADAR
ZARAR DA VEREBILIR.

  A seti (devam=True) : ikinci soru oncekine yaslaniyor, tek basina
                        anlamsiz. Baglamla duzelmesi beklenir.
  B seti (devam=False): ikinci soru GERCEKTEN YENI BIR KONU. Baglam
                        eklemek burada aramayi eski konuya cekerse
                        kazanc degil kayip olur.

B setini olcmeyen bir degerlendirme yaniltir: A'yi %20 iyilestirip
B'yi %30 bozan bir degisiklik net zarardir ve yalnizca A'ya bakan
biri bunu goremez.

HER KAYIT
    (onceki_soru, kisa_soru, tam_soru, kanun_no, madde_no, devam)

  onceki_soru : akista bir onceki soru (baglami ureten sey)
  kisa_soru   : kullanicinin gercekte yazdigi hali
  tam_soru    : ayni sorunun kendi basina ayakta duran hali. TAVAN
                olcumu bununla yapilir: "kullanici bastan acik acik
                yazsaydi" ne olurdu. Baglam kurma isinin hedefi bu
                tavana yaklasmak, onu asmak degil.
  kanun/madde : beklenen dogru kaynak. madde None ise yalnizca dogru
                kanunun bulunmasi beklenir.

Gold etiketler `python -m tests.dogrula_devam` ile kulliyattaki madde
basliklariyla karsilastirilip duzeltildi; elle yazilip dogrulanmadan
birakilmadi.
"""
from __future__ import annotations

Kayit = tuple[str, str, str, str, str | None, bool]

# ---------------------------------------------------------------- A seti
# Ikinci soru oncekine yasliyor: isaret zamiri ("bu", "buna", "bunda"),
# eksiltili yapi ("sinirri asilirsa"), ya da karsilastirma ("peki isveren
# icin"). Tek basina arandiginda sistemin bulmasi beklenmiyor.
DEVAM: list[Kayit] = [
    ("kirayi geciktiren kiracinin tahliyesi",
     "peki bu süre ne kadar",
     "kira bedelini ödemeyen kiracıya verilecek ödeme süresi ne kadardır",
     "6098", "315", True),

    ("işçinin haklı nedenle derhal fesih hakkı",
     "peki işveren için hangi hâller var",
     "işverenin haklı nedenle derhal fesih hakkı hangi hâllerde doğar",
     "4857", "25", True),

    ("yıllık ücretli izin süresi kaç gündür",
     "buna hak kazanmak için ne kadar çalışmak gerekir",
     "yıllık ücretli izne hak kazanmak için ne kadar çalışmak gerekir",
     "4857", "53", True),

    ("evlilik birliğinin sarsılması nedeniyle boşanma",
     "peki zina için ayrı bir sebep var mı",
     "zina nedeniyle boşanma davası",
     "4721", "161", True),

    ("hırsızlık suçunun cezası nedir",
     "nitelikli hâlleri neler",
     "nitelikli hırsızlık suçu ve cezası",
     "5237", "142", True),

    ("kişisel verilerin işlenme şartları",
     "ilgili kişinin bu konuda hakları neler",
     "kişisel verisi işlenen ilgili kişinin hakları nelerdir",
     "6698", "11", True),

    ("haksız fiil sorumluluğu",
     "bunda zamanaşımı kaç yıl",
     "haksız fiilden doğan tazminat isteminde zamanaşımı süresi",
     "6098", "72", True),

    ("meşru savunma",
     "sınırı aşılırsa ne olur",
     "meşru savunmada sınırın aşılması hâli",
     "5237", "27", True),

    ("işe iade davası şartları",
     "açma süresi ne kadar",
     "işe iade davası açma süresi",
     "4857", "20", True),

    ("nişanlılığın bozulmasında maddi tazminat",
     "manevi tazminat da istenebilir mi",
     "nişanın bozulması nedeniyle manevi tazminat",
     "4721", "121", True),

    ("ihtiyati tedbir kararı",
     "buna itiraz edilebilir mi",
     "ihtiyati tedbir kararına itiraz",
     "6100", "394", True),

    ("genel işlem koşulları",
     "yazılmamış sayılırsa sözleşmenin kalanı ne olur",
     "genel işlem koşullarında yazılmamış sayılmanın sözleşmeye etkisi",
     "6098", "22", True),

    ("mirasçılık belgesi",
     "reddetme süresi ne kadar",
     "mirasın reddi süresi",
     "4721", "606", True),

    ("kira bedelinin belirlenmesi",
     "beş yıldan sonra nasıl oluyor",
     "beş yıldan uzun süreli kira sözleşmelerinde kira bedelinin belirlenmesi",
     "6098", "344", True),

    ("dava dilekçesinde bulunması gerekenler",
     "eksik olursa ne olur",
     "dava dilekçesinde eksiklik bulunması hâlinde verilecek süre",
     "6100", "119", True),

    ("ihbar öneli süreleri nedir",
     "buna uymayan ne öder",
     "ihbar önellerine uymayan tarafın ödeyeceği ihbar tazminatı",
     "4857", "17", True),

    ("veri sorumlusunun aydınlatma yükümlülüğü",
     "buna uymazsa ceza var mı",
     "aydınlatma yükümlülüğüne aykırılıkta uygulanacak idari para cezası",
     "6698", "18", True),

    ("hakaret suçunun cezası",
     "kamu görevlisine karşı işlenirse ne olur",
     "kamu görevlisine görevinden dolayı hakaret suçunun cezası",
     "5237", "125", True),

    ("evlenme yaşı kaç",
     "istisnası var mı",
     "olağanüstü durumda hâkimin evlenmeye izin vermesi",
     "4721", "124", True),

    ("fazla çalışma ücreti nasıl hesaplanır",
     "yılda en fazla kaç saat olabilir",
     "fazla çalışma süresi yılda en çok kaç saat olabilir",
     "4857", "41", True),
]

# ---------------------------------------------------------------- B seti
# KONTROL SETI. Ikinci soru yeni bir konu ve kendi basina zaten
# anlamli; kisa ve tam hali ayni. Beklenti: baglam eklemek bu
# sorulardaki isabeti DUSURMEMELI.
KONU_DEGISIMI: list[Kayit] = [
    ("kirayi geciktiren kiracinin tahliyesi",
     "işverenin haklı nedenle derhal fesih hakkı",
     "işverenin haklı nedenle derhal fesih hakkı",
     "4857", "25", False),

    ("hırsızlık suçunun cezası nedir",
     "yıllık ücretli izin süresi kaç gündür",
     "yıllık ücretli izin süresi kaç gündür",
     "4857", "53", False),

    ("yıllık ücretli izin süresi kaç gündür",
     "evlenme yaşı kaç",
     "evlenme yaşı kaç",
     "4721", "124", False),

    ("kişisel verilerin işlenme şartları",
     "meşru savunma",
     "meşru savunma",
     "5237", "25", False),

    ("ihtiyati tedbir kararı",
     "kira bedelinin belirlenmesi",
     "kira bedelinin belirlenmesi",
     "6098", "344", False),

    ("boşanma sebebi zina",
     "veri sorumlusunun aydınlatma yükümlülüğü",
     "veri sorumlusunun aydınlatma yükümlülüğü",
     "6698", "10", False),

    ("haksız fiil sorumluluğu",
     "dolandırıcılık suçu",
     "dolandırıcılık suçu",
     "5237", "157", False),

    ("fazla çalışma ücreti nasıl hesaplanır",
     "dava dilekçesinde bulunması gerekenler",
     "dava dilekçesinde bulunması gerekenler",
     "6100", "119", False),

    ("hakaret suçunun cezası",
     "işe iade davası şartları",
     "işe iade davası şartları",
     "4857", "18", False),

    ("evlenme yaşı kaç",
     "hırsızlık suçunun cezası nedir",
     "hırsızlık suçunun cezası nedir",
     "5237", "141", False),
]

SORULAR: list[Kayit] = DEVAM + KONU_DEGISIMI
