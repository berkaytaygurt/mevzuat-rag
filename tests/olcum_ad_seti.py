"""Kisi adi tespiti icin COK TURLU belge seti.

NEDEN BU SET VAR

Ilk olcum tek bir sentetik delil tespiti dilekcesiyle yapildi ve 3/3
cikti. Ama istem o belgeye bakilarak yazilmisti -- yani sonuc, yontemin
degil o belgenin olcumu olabilirdi. Bu set ayni seyi yedi ayri belge
turu ve ISIM BICIMI uzerinde soruyor.

SETIN ZORLUKLARI (her biri bilerek kondu)

  1. Sirada adi olan isimler : Deniz, Baris, Gunes, Safak, Nil, Ozgur
     Turkcede bunlar hem isim hem sozluk kelimesi. Buyuk harf sezgisi
     de model de burada yanilabilir.
  2. Ilcesiyle ayni soyad     : "Ozgur Cankaya" kisi, "Cankaya/ANKARA" yer.
     Ayni kelime, biri maskelenmeli digeri maskelenmemeli.
  3. Bas harfli ad            : "M. Cufadar" -- gercek dilekcelerde sik.
  4. Imza blogundaki ad       : metnin sonunda, cumle icinde degil.
  5. Kurum icindeki kisi adi  : "Yilmaz Insaat Ltd. Sti." KURUMDUR,
     icindeki "Yilmaz" kisi adi degil.
  6. Hic isim olmayan belge   : yanlis pozitif testi. Bir sey bulursa
     gurultu uretiyor demektir ve avukatin guvenini bitirir.
  7. Uc isimli kisi           : "Ayse Nur Demirtas" -- iki kelimelik ad.

HER KAYIT
    (etiket, belge_metni, [gold_isimler], [asla_listelenmemeli])

Ikinci liste birinci kadar onemli: kacirmanin bedeli veri sizmasi,
fazla isaretlemenin bedeli okunmaz bir liste ve terk edilen bir ozellik.

BU ISIMLER UYDURMADIR. Gercek kisilere ait degildir; ad ve soyadlar
zorluk uretmek icin kasitli olarak birlestirildi.
"""
from __future__ import annotations

Kayit = tuple[str, str, list[str], list[str]]

BELGELER: list[Kayit] = [
    # ---------------------------------------------------------------
    ("is-hukuku-bas-harfli",
     """ANKARA 7. İŞ MAHKEMESİ SAYIN HÂKİMLİĞİ'NE

DAVACI  : M. Cufadar
VEKİLİ  : Av. Şafak Erdoğmuş
DAVALI  : Yılmaz İnşaat Sanayi ve Ticaret Limited Şirketi

KONU : İşe iade ve kıdem tazminatı talebimizden ibarettir.

AÇIKLAMALAR

1. Müvekkil M. Cufadar, davalı şirkette 2019 yılından bu yana usta
olarak çalışmaktadır. İş sözleşmesi, savunması alınmaksızın feshedilmiştir.

2. Fesih sırasında işyerinde bulunan tanık Deniz Kalaycıoğlu, müvekkile
herhangi bir savunma hakkı tanınmadığını beyan etmektedir.

3. Bordroları düzenleyen muhasebeci Barış Sungurlu da ödemelerin eksik
yapıldığını doğrulamaktadır.

SONUÇ : Feshin geçersizliğine karar verilmesini talep ederiz.

Av. Şafak Erdoğmuş""",
     ["M. Cufadar", "Şafak Erdoğmuş", "Deniz Kalaycıoğlu", "Barış Sungurlu"],
     ["Yılmaz İnşaat Sanayi ve Ticaret Limited Şirketi", "Yılmaz İnşaat",
      "İş Mahkemesi", "Ankara"]),

    # ---------------------------------------------------------------
    ("bosanma-sozluk-kelimesi-isimler",
     """İZMİR 4. AİLE MAHKEMESİ'NE

DAVACI : Nil Irmakoğlu
DAVALI : Güneş Irmakoğlu
MÜŞTEREK ÇOCUK : Umut Irmakoğlu (2016 doğumlu)

KONU : Boşanma, velayet ve nafaka talebimizdir.

AÇIKLAMALAR

Taraflar 2014 yılında evlenmiştir. Müvekkil Nil Irmakoğlu ile davalı
Güneş Irmakoğlu arasındaki ortak hayat çekilmez hale gelmiştir.

Müşterek çocuk Umut Irmakoğlu'nun velayetinin müvekkile verilmesini,
kendisi için tedbir nafakası bağlanmasını talep ediyoruz.

Komşuları Özgür Çankaya olayların tanığıdır.

Adres : Alsancak Mahallesi, Konak/İZMİR""",
     ["Nil Irmakoğlu", "Güneş Irmakoğlu", "Umut Irmakoğlu", "Özgür Çankaya"],
     ["Aile Mahkemesi", "Alsancak", "Konak", "İzmir", "Çankaya/İZMİR"]),

    # ---------------------------------------------------------------
    ("ceza-iddianame",
     """BURSA CUMHURİYET BAŞSAVCILIĞI
SORUŞTURMA NO : 2025/8841

ŞÜPHELİ : Erdinç Kavaklıoğlu
MÜŞTEKİ : Ayşe Nur Demirtaş
SUÇ : Hırsızlık

Şüpheli Erdinç Kavaklıoğlu'nun, müştekiye ait işyerinin kilidini gece
vakti kırarak içeri girdiği tespit edilmiştir.

Olay yerinde bulunan güvenlik görevlisi Tolga Şenocak, şüpheliyi teşhis
etmiştir. Kamera kayıtları bilirkişi Hakan Ürgüplü tarafından
incelenmiştir.

Türk Ceza Kanunu'nun 142. maddesi uyarınca cezalandırılması talep
olunur.""",
     ["Erdinç Kavaklıoğlu", "Ayşe Nur Demirtaş", "Tolga Şenocak",
      "Hakan Ürgüplü"],
     ["Cumhuriyet Başsavcılığı", "Türk Ceza Kanunu", "Bursa"]),

    # ---------------------------------------------------------------
    ("ihtarname-imza-blogu",
     """İHTARNAME

KEŞİDECİ : Sevim Bozkurtlu
MUHATAP  : Kaya Tekstil Anonim Şirketi

Sözleşmeden doğan alacağımızın ödenmesi için tarafınıza daha önce
bildirimde bulunulmuştur. İşbu ihtarnamenin tebliğinden itibaren yedi
gün içinde ödeme yapılmadığı takdirde yasal yollara başvurulacaktır.

Saygılarımızla,

Sevim Bozkurtlu
Vekili Av. Rüçhan Alparslan""",
     ["Sevim Bozkurtlu", "Rüçhan Alparslan"],
     ["Kaya Tekstil Anonim Şirketi", "Kaya Tekstil"]),

    # ---------------------------------------------------------------
    ("icra-kurum-ve-kisi",
     """ANKARA 12. İCRA MÜDÜRLÜĞÜ'NE
DOSYA NO : 2025/4471 E.

ALACAKLI : Demirsoy Gıda Pazarlama Limited Şirketi
BORÇLU   : Necdet Yalçınkaya

Borçlu Necdet Yalçınkaya aleyhine başlatılan takibe itiraz edilmiş
olup, itirazın iptali talep edilmektedir.

Şirket yetkilisi Perihan Aksoylu'nun beyanı dosyaya sunulmuştur.""",
     ["Necdet Yalçınkaya", "Perihan Aksoylu"],
     ["Demirsoy Gıda Pazarlama Limited Şirketi", "Demirsoy Gıda",
      "İcra Müdürlüğü"]),

    # ---------------------------------------------------------------
    ("bilirkisi-raporu",
     """BİLİRKİŞİ RAPORU

Rapor düzenleyen : Makine Mühendisi Cengizhan Bayraktutan
İnceleme tarihi  : 11.02.2026

Mahkemenizce görevlendirilmem üzerine, davacı Melahat Özkeskin'e ait
taşınmazda keşif yapılmıştır. Keşifte davalı vekili Av. Yıldırım
Hacıosmanoğlu da hazır bulunmuştur.

Yapının taşıyıcı sisteminde imalat hatası bulunduğu kanaatine
varılmıştır.""",
     ["Cengizhan Bayraktutan", "Melahat Özkeskin", "Yıldırım Hacıosmanoğlu"],
     ["Bilirkişi Raporu", "Makine Mühendisi"]),

    # ---------------------------------------------------------------
    # YANLIS POZITIF TESTI: hic kisi adi yok.
    ("isimsiz-kanun-metni",
     """DİLEKÇE

KONU : Yürütmenin durdurulması istemimizdir.

4857 sayılı İş Kanunu'nun 18. maddesi ile 6100 sayılı Hukuk
Muhakemeleri Kanunu'nun 389. maddesi uyarınca, Danıştay İdari Dava
Daireleri Kurulu'nun yerleşik içtihadı gözetilerek yürütmenin
durdurulmasına karar verilmesini talep ederiz.

İdare Mahkemesi Başkanlığına sunulmak üzere Bölge İdare Mahkemesi
kanalıyla iletilmiştir.""",
     [],
     ["İş Kanunu", "Hukuk Muhakemeleri Kanunu", "Danıştay",
      "İdare Mahkemesi", "Bölge İdare Mahkemesi"]),
]
