"""Gemini ile uretilmis kucuk olcum seti (40 soru).

Yerel modelin uretiminden belirgin sekilde temiz: dogal Turkce, dogru
dilbilgisi, gunluk dil. Kucuk olmasinin sebebi Gemini ucretsiz katmaninin
MODEL BASINA GUNDE 20 istek vermesi (quotaValue=20); daha fazlasi ancak
ucretli anahtarla ya da gunlere yayarak uretilebilir.

Ayirt etme gucu dusuk (40 soru); ayar karsilastirmasi icin degil, uretim
kalitesini gormek ve elle inceleme icin tutuluyor.

Her soru, karsisindaki maddeden uretildi; dogru cevap o maddedir.
Sentetik oldugu icin gercek kullanici sorularindan daha iyimser sonuc
verir; mutlak dogruluk olcusu degil, degisiklikleri karsilastirma
olcegidir.
"""

SORULAR: list[tuple[str, str, str | None]] = [
    ('Hangi kitapların basılacağına veya satın alınacağına kim karar verir?', '34041', '8'),
    ('Devletin haberleşme kurumuyla borçlarım için dava bitmeden anlaşma yapabilir miyim?', '38446', '5'),
    ('Üniversitedeki engelliler merkezi ne tür çalışmalar ve hizmetler yürütür?', '38780', '6'),
    ('Üretilen tütün ve malların piyasadaki satışı neye göre yapılır?', '12662', '54'),
    ('Yüksek lisans yaparken dönem kaydımı yenilemezsem ne olur?', '39556', '13'),
    ('Eskişehir Osmangazi Üniversitesindeki Atatürk İlkeleri Araştırma Merkezi ne amaçla kurulmuştur?', '34767', '1'),
    ('Üniversite merkez yönetim ekibi kimlerden oluşur ve senede kaç kere toplanır?', '33859', '10'),
    ('Danışma kurulu tam olarak ne iş yapar, görevleri nelerdir?', '42445', '13'),
    ('Sanayi tesislerinin gerekli işlemleri tamamlaması için ne kadar süresi var?', '5201', 'Geçici 2'),
    ('Şirketimizin adres veya yetkili değişikliklerini hangi kuruma bildirmek zorundayız?', '18936', '32'),
    ('Mezun olmak için tek ders sınavına girme şartları nelerdir?', '33808', '28'),
    ('Hakimi mahkemeye verirken kanıtlarımı ve belgelerimi eklemek zorunda mıyım?', '6100', '48'),
    ('Yeni kadro açma ve değiştirme işlemleri hangi kurallara göre yapılır?', '38355', '5'),
    ('Balık ve su canlılarının sağlık kuralları neye göre belirleniyor?', '15854', '3'),
    ('Devlet kurumu ihale şartnamesini dışarıdan birine hazırlatabilir mi?', '9', '17'),
    ('Babamdan miras kalan subay kılıcı için ruhsat almam gerekir mi?', '911779', '58'),
    ('Savcılar hazırlanan raporlar hakkındaki görüşlerini kaç gün içinde bildirmek zorundadır?', '15617', '6'),
    ('Kaldıraçlı işlemlerde yatırdığım paradan daha fazla zarar edebilir miyim?', '18576', '24'),
    ('Ani denetimde trafom düzgün çalışmazsa ne tür bir işlem yapılır?', '11450', '12'),
    ('Askeri işyerlerini kim denetler?', '18727', '6'),
    ('Bir merkezin müdürü tam olarak ne iş yapar?', '38814', '9'),
    ('İhale teklifimdeki hesap hatası yüzünden elenir miyim?', '24571', '41'),
    ('Şirket ortağı olarak haklarımı nasıl kullanabilirim?', '6102', '426'),
    ('Bu mesleki yeterlilik kuralları hangi yasalara göre çıkarıldı?', '12061', '3'),
    ('Haberleşme frekanslarının sınırlarını ve kurallarını nereden öğrenebilirim?', '13181', '6'),
    ('Namık Kemal Üniversitesi kadın merkezi yazılarındaki kısaltmalar ne anlama geliyor?', '36203', '4'),
    ('Yedek asker olarak eğitime çağrıldığımda ödeme alır mıyım?', '2941', 'Ek 1'),
    ('MTA vazgeçtiği ama henüz satılmayan maden yerlerini geri alabilir mi?', '3213', 'Geçici 13'),
    ('Kas hastalıkları tedavi merkezlerini kim denetler ve yönlendirir?', '38662', '6'),
    ('Seçim kampanyaları ne zaman başlar ve ne zaman biter?', '298', '49'),
    ('Orman müdürlüğü bu yönetmeliği neye dayanarak hazırladı?', '35996', '2'),
    ('Gümrükten geçecek bitkimin paketi zarar görürse ne yapmalıyım?', '63346', '33'),
    ('İhaleye girmek için evrakları satın almak zorunda mıyım?', '703', '11'),
    ('İhaleye girerken ne kadar güvence parası yatırmam gerekir?', '38295', '21'),
    ('Doktora tez sunumundan kaç kez kalırsam okuldan atılırım?', '40969', '55'),
    ('Belgemde güncelleme yapıldığında yeni evraklarımı ne zaman teslim alırım?', '19969', '31'),
    ('Gaz alım komisyonu kaç kişiden kurulur ve kimler üye olamaz?', '11549', '11'),
    ('2013 öncesi tezsiz yüksek lisans mezunları doktora yapabilir mi?', '39556', 'Geçi̇ci̇ 1'),
    ('Yurt dışı eğitimimden sonra devlet bana iş vermezse ne olur?', '1416', '18'),
    ('Yeni kurallara uymayan ürünümün satış iznini ne zamana kadar güncellemeliyim?', '14404', 'Geçi̇ci̇ 5')
]
