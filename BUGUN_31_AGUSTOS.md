# 31 Ağustos — yapılanlar

## 1. Külliyatın %28'i indekse hiç girmemiş (çözüldü)

4.099 belge kayıptı. İki ayrı sessiz hata:

**PDF adresi tür bazında farklı.** Adres `/MevzuatMetin/{tur}.{tertip}.{no}.pdf`
kalıbıyla kuruluyordu. Tebliğ ve iki yönetmelik türünde doğrusu
`/MevzuatMetin/yonetmelik/...`. Alt dizin atlanınca sunucu 404 vermiyor, boş
bir PDF döndürüyordu — yani hata görünmüyordu.

**Madde başlığı olmayan belgeler atılıyordu.** Tebliğlerin önemli kısmı
numaralı madde içermiyor. Madde arayan ayrıştırıcı bunları boş dönüyor, belge
tümüyle kayboluyordu. Artık paragraflara bölünüp saklanıyor (2.150 parça).

**Katalog da eksikti.** Liste isteği 3.000. kayıtta hata veriyordu, 4 denemede
pes ediliyordu. Kalıcı sınır sanılmıştı — değilmiş. Deneme 8'e çıkarılınca üç
tür de eksiksiz geldi.

| Tür | Sabah | Şimdi |
|---|---|---|
| Tebliğ | %43 | %66 |
| Kurum Yönetmeliği | %28 | %67 |
| CB Yönetmeliği | %64 | %82 |

İndirme sürüyor, oranlar artmaya devam edecek.

## 2. Kendi açtığım hata (bulundu, düzeltildi)

Düz metin yedeği, sunucunun "Sayfada Çalışma Yapılmaktadır" bakım sayfasını
gerçek belge sanıp **68 çöp kayıt** indeksledi. Bakım sayfası 10.832 karakter
metin taşıyor, yani "içerik var" gibi görünüyor.

Üç ayrı sahte PDF varmış: 60.487 (belge bulunamadı), 64.854 (boş),
259.488 (bakım). Üçü de artık tanınıyor, ayrıca metin içeriğinden de
kontrol ediliyor. 68 kayıt silindi, teste bağlandı.

## 3. Mahkeme kararları çalışıyor

Dün iki sorun vardı, ikisi de çözüldü:

| Sorun | Dün | Bugün |
|---|---|---|
| WAF engeli | 15 istekte kesiyordu | 12 sn aralıkla sorunsuz |
| İlgisiz sonuç | 11 kararın 0'ı ilgili | 5/5 ilgili |

**Gerekçe ayıklama denendi, bırakıldı.** Kod gerekçeyi `GEREĞİ DÜŞÜNÜLDÜ`
ifadesiyle buluyordu. 15 gerçek kararda ölçüldü: bu ifade **hiçbirinde yok**.
Notlarda önerilen alternatif de yok. Kararların %70'inde böyle bir işaret
bulunmuyor; kod sessizce "metnin ikinci yarısını al" yedeğine düşüyordu.
Şimdi künye atılıyor (karar başına ~422 karakter), kalan metin parçalanıyor.

Kararlar **ayrı indekste** tutuluyor — tek indekste birleştirilse maddeleri
sıradan iterlerdi. Arayüzde ayrı bölüm, cevapta ayrı başlık.

## 4. Gemini ücretsiz katmanı: günde 20 istek

`quotaValue: 20` — model başına, günde. Dün "kotayı yaktım" demiştim;
yakmamışım, limit zaten buymuş. İki sonucu var:

- Ölçüm seti Gemini ile üretilemez (günde ~60 soru)
- **Site Gemini ile demo edilemez** — 20 soru sonra susar

Site şu an yerel modelde. Avukata göstereceksen ücretli anahtar gerekiyor;
Flash'ın ücretli katmanı milyon token ~0,3 dolar.

## 5. Doğruluk hakkında öğrenilen

Üç ölçüm setinde birden ölçüldü:

| Set | MRR |
|---|---|
| El yazımı (34 soru) | 0,724 |
| Yerel model üretimi (150) | 0,446 |
| **Gemini üretimi (40)** | **0,250** |

Gemini'nin soruları düzgün Türkçe ve doğal — ve sistem onlarda çok daha kötü.
Tek bir örnekte de aynı şey görüldü:

| Sorgu | Doğru maddenin sırası |
|---|---|
| "kıdem tazminatı şartları" | 1 |
| "kıdem tazminatı" | 8 |
| "kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir" | 21 |

Yani sistem **anahtar kelimeyle iyi, doğal cümleyle kötü** — insanlar ise
ikincisi gibi soruyor. Asıl geliştirme alanı burası.

## 6. Doğal dilde arama için bir deneme

Ölçüm bir ipucu verdi: aynı bilgiyi soran iki sorgudan anahtar kelime hâli
1. sırayı, doğal cümle 21. sırayı veriyordu. Aradaki tek fark soru kelimeleri
— kanun metninde "ne kadar", "gerekir mi", "nasıl" geçmiyor, bu kelimeler
vektörü konudan uzaklaştırıyor.

Denenen çözüm: sorgunun bir de soru kalıplarından arındırılmış hâlini aratıp
iki sonucu birleştirmek. LLM gerektirmiyor, maliyeti tek bir ek gömme (~30 ms).

    "kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir"
      -> "kıdem tazminatına hak kazanmak için çalışmak"

Zaten anahtar kelime olan sorgularda ("kıdem tazminatı şartları") çekirdek boş
dönüyor ve ikinci arama hiç yapılmıyor, yani o sorguları etkilemiyor.

Ölçüldü: kazanç küçük (224 soruda 3 soru) ama üç sette de negatif değil.
Açık bırakıldı.

İlk sürümde bir tasarım hatası vardı — çekirdek sentetik soruların %100'ünde
devreye giriyordu, çünkü sadece soru işaretini silmek bile "değişti"
sayılıyordu. İkinci arama birincinin neredeyse aynısını arayıp gürültü
ekliyordu ve yerel sette ilk-5 isabetini 85'ten 83'e düşürmüştü. Artık
yalnızca gerçek soru kelimesi atıldığında çalışıyor.

## 8. Asıl kazanç: sıralayıcı maddenin sadece başını görüyormuş

Çekirdek sorgu ararken daha güçlü bir açıklama buldum. Sıralama modeli
maddenin ilk 256 token'ini (~768 karakter) görüyor. Külliyatta **58.975 madde
(%34) bundan uzun**. Başarısız örnekteki madde 2.002 karakter — model
yalnızca %38'ine bakarak sıralıyordu.

Görülen metin 512 token'e çıkarıldı:

| max_seq | El (34) | Yerel (150) | Gemini (40) | Süre |
|---|---|---|---|---|
| 256 | 0,744 | 0,447 | 0,258 | 1,21 sn |
| 384 | 0,718 | 0,457 | 0,261 | 1,35 sn |
| **512** | 0,722 | **0,474** | **0,261** | 1,45 sn |

En büyük sette üç değer boyunca **tek yönlü artış** — rastgele dalgalanma
böyle sıralanmaz. İlk-5 isabeti 85'ten 89'a çıktı. El setindeki 2 soruluk
düşüş o setin gürültü sınırında.

Tek örnekte de doğrulandı: kıdem tazminatı sorusunda doğru madde **21.
sıradan 6. sıraya** çıktı. İlk 5'e girmiyor ama modele 10 madde
gönderildiği için artık cevaba dahil oluyor.

Bedeli %20 süre (1,21 → 1,45 sn) ve yığın boyutunun 12'den 6'ya inmesi —
4 GB VRAM'de uzun dizi ile 12'lik yığın sığmıyor.

## 7. İki gerileme açtım, ikisini de buldum

**Bakım sayfası indekslendi** (68 kayıt) — düz metin yedeği, sunucunun
"Sayfada Çalışma Yapılmaktadır" sayfasını gerçek belge sandı. Üç sahte PDF
boyutu artık tanınıyor, metin içeriğinden de kontrol ediliyor.

**HTML yedeği devre dışı kaldı.** Sahte PDF'lerde boş bayt döndürmeye
başlayınca `parse_pdf` hata atmaya başladı; hata da HTML yedeğini atlattı.
Başarısızlık oranı %2,5'ten %50'ye fırlamıştı. Düzeltildi, ikisi de teste
bağlandı.

Bunları yazmamın sebebi şu: ikisi de **sessiz** hatalardı — sistem çalışıyor
görünüyordu. Bu projedeki hataların çoğu böyle çıkıyor, o yüzden her
değişiklikten sonra sayıya bakmak gerekiyor.

## Bekleyen

- Mevzuat indirmesi sürüyor (~10 saat kaldı)
- İçtihat indirmesi sürüyor
- İkisi bitince **yeniden indeksleme** gerekiyor (~2 saat GPU)
- Ölçüm ancak ondan sonra anlamlı

## Bir risk

`mevzuat-rag` klasörünün kendi git deposu yok. Bugüne kadarki işin tamamı
versiyon kontrolü dışında. Kaynak kodun yedeği alındı
(`data/yedek/kod_20260831`) ama düzgün çözüm bir depo kurmak.
