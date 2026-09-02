# Aibars

*Türk mevzuatında soru sorabildiğiniz bir arama sistemi.
Bu belge ne yapmaya çalıştığımızı, ne bulduğumuzu ve neyin işe yarayıp
yaramadığını anlatır.*

---

## Çözmeye çalıştığımız şey

Bir avukatın "kıdem tazminatı için ne kadar çalışmak gerekir" sorusunun
cevabını bulması gerektiğinde iki yolu var.

**Birincisi mevzuat.gov.tr.** Devletin sitesi, ücretsiz ve eksiksiz. Ama
kelime araması yapıyor. "Kıdem tazminatı" yazarsınız, yüzlerce sonuç gelir,
hangisinin işinize yaradığını tek tek bakarak bulursunuz.

**İkincisi bir yapay zekâya sormak.** Cevabı hemen verir. Ama iki sorun var:
kaynağını gösteremez, ve bilmediği yerde uydurur — üstelik uydurduğunu belli
etmez, aynı kendinden emin tonla söyler.

Aibars bu ikisinin arasını doldurmayı deniyor: soruyu doğal dille sorun,
cevabı ilgili kanun maddesinin **tam metniyle birlikte** alın.

---

## Nasıl çalışıyor

Bir soru yazdığınızda üç şey oluyor.

**Önce arama.** Sistem 275 bin madde içinde sorunuza en yakın olanları
buluyor. Kelime eşleştirmiyor, anlam eşleştiriyor — "işten atıldım param ne
olur" ile kıdem tazminatı maddesini bir araya getirebiliyor.

**Sonra okuma.** Bulunan 10 maddenin tam metni bir yapay zekâ modeline
veriliyor ve şu deniyor: *yalnızca bunlara dayanarak cevapla.* Model kendi
hafızasından konuşmuyor; önüne konan metni okuyup açıklıyor.

**Sonra gösterme.** Cevabın altında dayanak maddeler tam metinleriyle
listeleniyor, her birinin yanında mevzuat.gov.tr bağlantısı var. İsterseniz
açıp okuyorsunuz.

Bu yöntemin adı RAG. Alternatifi modeli mevzuatla eğitmekti, ama o yanlış
olurdu: kanunlar değişir, her değişiklikte yeniden eğitim gerekir, ve
eğitilmiş model yine kaynak gösteremez.

---

## Elimizde ne var

**275.806 madde.** 10.601 belge — kanunlar, tüzükler, yönetmelikler,
tebliğler. Kağıda dökülse yaklaşık 99.600 sayfa.

Kanunların %99'u var. Yönetmelik ve tebliğlerde kapsam %66-82 arasında;
sitenin listeleri yarıda kesmesi ve belge adreslerinin türden türe değişmesi
yüzünden bir kısmı alınamadı. Kanun hükmünde kararnameler siteden hiç
sunulmuyor.

**2.890 Yargıtay kararı.** Hepsi iş hukuku — 9., 22. ve 7. Hukuk Daireleri.
Kararlar maddelerden ayrı tutuluyor ve cevapta ayrı bir bölüm olarak
gösteriliyor. Sebebi basit: karar bağlayıcı kural değil, kuralın bir olayda
nasıl uygulandığının örneği. İkisi karışmamalı.

---

## Asıl soru: buna gerek var mı

Doğrudan bir yapay zekâya sorsak ne kaybederiz? Bunu tahmin etmek yerine
ölçtük. İki test yapıldı.

### Birinci test: iş hukuku

Bir avukatın pratikte sorduğu 52 soru elle yazıldı — kıdem tazminatı, işe
iade, fazla mesai, yıllık izin gibi. Aynı sorular hem Aibars'a hem doğrudan
Gemini'ye soruldu.

**Sonuç: fark yok.** İkisi de benzer isabetle cevapladı.

Bunun sebebi anlaşılır. İş Kanunu internette binlerce kez yazılmış,
tartışılmış, örneklenmiş. Yapay zekâ onu zaten biliyor. 275 bin maddelik bir
külliyat kurmanın orada bir katkısı yok.

### İkinci test: kimsenin bilmediği mevzuat

Asıl fark burada olmalıydı. Tebliğ ve kurum yönetmeliklerinden 50 soru
seçildi — bir üniversitenin devam zorunluluğu oranı, bir odanın genel kurul
süresi, bir tebliğdeki hesaplama oranı gibi. Cevabı hep somut bir sayı.

| | Doğru cevap |
|---|---|
| Doğrudan Gemini | %57 |
| **Aibars** | **%91** |

Gemini'nin yanlışları uydurmaydı: doğrusu 3 iken 4 dedi, doğrusu 17 iken 9
dedi, doğrusu 50 iken "%40 ve %60" dedi. Hiçbirinde tereddüt etmedi.

Aynı soruların ilk 10'u Claude'a da soruldu; o da **2/10** yaptı.

### Bundan çıkan sonuç

Değer, yapay zekânın daha akıllı olmasında değil. Cevabı yine aynı model
yazıyor. Fark şu: **doğru metni bulup onun önüne koyuyoruz.**

Bilinen kanunlarda bunun anlamı yok, model zaten biliyor. Bilinmeyen
mevzuatta anlamı büyük, çünkü orada model tahmin ediyor.

Kısacası: *bildiğiniz kanunları sormayın, bilmediklerinizi sorun.*

---

## Sistemin zayıf yanı

En büyük sorun şu: **soru ne kadar doğal yazılırsa isabet o kadar düşüyor.**

Aynı bilgiyi soran üç sorgu:

| Ne yazarsanız | Doğru madde kaçıncı sırada |
|---|---|
| kıdem tazminatı şartları | 1. |
| kıdem tazminatı | 8. |
| kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir | 21. |

Üçü de aynı şeyi soruyor. Ama insanlar üçüncüsü gibi soruyor.

Sebep: kanun metni hukuk diliyle yazılmış, kullanıcı gündelik dille soruyor.
"Ne kadar", "gerekir mi", "nasıl" gibi kelimeler kanunda geçmiyor ve aramayı
konudan uzaklaştırıyor.

**Denenen çözüm:** soruyu aramadan önce yapay zekâya verip hukuk terimlerine
çevirtmek.

> "işten çıkarıldım tazminat alabilir miyim"
> → *kıdem tazminatı, ihbar tazminatı, iş sözleşmesinin feshi, iş güvencesi*

Bu işe yarıyor: elle yazılmış sorularda isabet 0,71'den 0,84'e çıkıyor. Uzun
süre kullanılamaz göründü çünkü 22 saniye sürüyordu. Sonra anlaşıldı ki sorun
tasarımda değil, seçilen modelde — küçük bir model aynı işi 48 kat hızlı
yapıyor. Şimdi 1,6 saniye.

---

## Yol boyunca bulunanlar

Sistem kurulurken çıkan hataların ortak özelliği vardı: **hiçbiri hata mesajı
vermiyordu.** Her şey çalışıyor görünüyordu.

- Türk Medeni Kanunu 1030 madde yerine 425 madde olarak indi. Sitenin verdiği
  sayfa uzun kanunları sessizce kesiyordu; PDF'e geçilince düzeldi.
- Aynı numarayı taşıyan farklı kanunlar birbirini eziyordu — 104 madde hiç
  indekse girmemişti.
- Yürürlükten kalktığı sanılan 54 maddenin 20'si aslında yürürlükteydi;
  yalnızca bir fıkrası kaldırılmıştı.
- 4.099 belge boş dosya olarak iniyordu. Belge adresi türden türe
  değişiyormuş ve yanlış adres, hata yerine boş bir PDF döndürüyormuş.
  Düzeltilince kapsam %30'dan %73'e çıktı — yeni bir çalışmayla değil, var
  olanın neden alınamadığının bulunmasıyla.
- Mahkeme kararlarının gerekçesi belirli bir ifadeyle bulunuyordu. 15 gerçek
  kararda sayıldı: o ifade **hiçbirinde yoktu.** Kod sessizce metnin ikinci
  yarısını alıyor ve gerekçenin başını kesiyordu.

Arama tarafında ölçülerek yapılan iyileştirmeler isabeti %35'ten %71'e
çıkardı. En sağlam kazanç şuydu: sıralama modeli maddenin yalnızca ilk 768
karakterini görüyordu, oysa külliyattaki 58.975 madde bundan uzun. Görülen
metin iki katına çıkarıldı.

---

## Dürüst değerlendirme

**Kanıtlanan:** bilinmeyen mevzuatta bu sistem, doğrudan yapay zekâdan
belirgin şekilde daha doğru. %91'e karşı %57, ve bu fark ölçüldü.

**Kanıtlanmayan:** genel olarak daha iyi olduğu. İş hukuku gibi bilinen
alanlarda fark yok, ve bunu gösteren bir ölçüm de yapılmadı.

**Eksik olanlar:**

- Doğal dilde arama hâlâ zayıf. Çözüm bulundu ama tam oturmadı.
- İçtihat yalnızca iş hukukunda. Kira, boşanma, ceza yok.
- Kapsam %73. Aradığınız tebliğ dörtte bir ihtimalle sistemde yok — ve sistem
  bunu size söyleyemiyor.
- **Hiçbir avukat denemedi.** Değerli olduğunu ölçtük, gerçekten
  kullanılabilir olduğunu bilmiyoruz.

Sonuncusu en önemlisi. Bir hukukçunun bir saat kullanması, beş yüz sentetik
sorudan daha çok şey öğretir.

---

## Sayılarla

| | |
|---|---|
| Madde | 275.806 |
| Belge | 10.601 |
| Mahkeme kararı | 2.890 |
| Arama süresi | ~2 saniye |
| Cevap süresi | ~5 saniye |
| Otomatik test | 132 |
| Aylık maliyet | Birkaç dolar |
| Donanım | Bir dizüstü bilgisayar |

*Ayrıntılı ölçüm kayıtları ve yöntem notları için depodaki README ve test
betiklerine bakılabilir.*
