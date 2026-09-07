# Aibars

Türk mevzuatı ve içtihadı üzerinde çalışan bir hukuk arama asistanı.
Avukat kendi diliyle bir soru yazar; sistem ilgili kanun maddelerini,
karşı tarafın dayanabileceği maddeleri ve Yargıtay kararlarını
kaynağıyla birlikte getirir.

Bu belge sistemin **son halini** anlatır: veri nereden geliyor, arama
nasıl çalışıyor, sitede ne var.

---

## 0. Bu nedir, ne değildir

### Nedir

Aibars bir **arama** aracıdır. Türkiye'nin yürürlükteki mevzuatının
tamamı ve Yargıtay kararları üzerinde çalışır. Avukat kendi diliyle
soru yazar — hukuki terim bilmesi gerekmez — sistem ilgili maddeleri
bulur, kısa bir cevap yazar ve **her cümlenin dayanağını gösterir**.

Cevaptaki her madde numarası ve her sayı, gerçek madde metniyle
karşılaştırılır. Tutmuyorsa cevap gösterilmez.

### Ne değildir

- **Hukuki görüş vermez.** "Davayı kazanırsın", "şu argümanı kullan",
  "süren doldu" demez.
- **Ezberden konuşmaz.** Yapay zekâ modelinin hafızasındaki hukuk
  bilgisi kullanılmaz; cevap yalnızca sistemin bulduğu gerçek madde
  metinlerinden üretilir.
- **Sohbet botu değildir.** Konuşma geçmişi üzerinden akıl yürütmez;
  her soru kendi başına aranır.
- **Karar mercii değildir.** Getirdiği maddeler bir liste, bir
  başlangıç noktasıdır. Çıkarım avukatın.

### Yapay zekâ tam olarak nerede

Sistemin üç yerinde yapay zekâ var, üçü de **yardımcı** roldedir:

| Nerede | Ne yapıyor | Neden gerekli |
|---|---|---|
| Soruyu çevirme | Soruyu kanun diline / hukuki terime çevirir | Avukat "kiracımı çıkarabilir miyim" der, kanun "kira sözleşmesinin feshi" yazar |
| Anlam eşleştirme | Soru ile madde metnini anlamca karşılaştırır | Kelime araması "muris muvazaası"nı bilmeyen kullanıcıya bir şey bulamaz |
| Cevap yazma | Bulunan maddelerden kısa bir özet yazar | Avukat 10 maddeyi baştan okumak zorunda kalmasın |

**Nerede YOK:** Kanun metinlerinde. Gösterilen her madde
mevzuat.gov.tr'den gelen **birebir resmî metindir**; model onu
yeniden yazmaz, özetlemez, düzeltmez. Kararlar da Yargıtay'ın kendi
metnidir.

Bu ayrım sistemin bel kemiğidir: model yalnızca *bulmaya* ve
*özetlemeye* yarar, *hüküm üretmeye* değil.

### Canlı olan kısım tam olarak nerede

| Parça | Nerede duruyor |
|---|---|
| Kanun, yönetmelik, tebliğ (275.192 madde) | **Diskte** — bir kez indirildi |
| Madde-madde atıf grafiği (105.937 bağlantı) | **Diskte** — metinden türetildi |
| Yargıtay kararları | **Kısmen diskte** (7.566), gerisi **canlı internetten** |
| Danıştay kararları | Neredeyse tamamı **canlı internetten** |

Yani: **mevzuat sabittir, içtihat canlıdır.** Sebebi basit — kanun
sayısı bellidir (14.439 mevzuat), indirilebilir; Yargıtay'da
milyonlarca karar vardır, indirmekle bitmez.

Canlı çekim **her soruda çalışmaz**. Önce yerel arşive bakılır; orada
karşılık yoksa ya da kullanıcı "Daha fazla karar getir" derse
Yargıtay'ın sitesine gidilir.

### Ne kullanıldı

| Ne için | Ne kullanıldı | Nerede çalışıyor |
|---|---|---|
| Soruyu anlamca maddelerle eşleştirmek | Qwen3-Embedding-0.6B | Kendi bilgisayarında |
| Adayları eleyip sıralamak | bge-reranker-v2-m3 | Kendi bilgisayarında |
| Birebir kelime araması | BM25 (klasik yöntem, yapay zekâ değil) | Kendi bilgisayarında |
| Cevap yazmak, soruyu çevirmek | Google Gemini Flash Lite | Google'ın sunucusunda |
| Site altyapısı | FastAPI + tek dosya HTML | Kendi bilgisayarında |
| Veri kaynakları | mevzuat.gov.tr, karararama.yargitay.gov.tr | — |

Arama yapan iki model **senin bilgisayarında** çalışır; dışarı
yalnızca cevabı yazdırmak için Google'a gidilir. Mevzuat külliyatı ve
avukatın dosyaları hiçbir zaman dışarı çıkmaz.

---

## 1. Bir soru sorulduğunda ne oluyor

```
         avukat bir soru yazar
                  |
                  v
    +------------------------------+
    | 1. Soru kanun diline çevrilir|   ayrıntı aşağıda
    +------------------------------+
                  |
                  v
    +------------------------------+
    | 2. Dört ayrı yoldan aranır   |   - madde numarası ("TBK 344")
    |    ve sonuçlar birleştirilir |   - anlam
    |                              |   - kelime
    |                              |   - sorunun kendi hâli
    +------------------------------+
                  |
                  v
    +------------------------------+
    | 3. En iyi 50 aday yeniden    |   ikinci bir model her adayı
    |    sıralanır                 |   soruyla tek tek karşılaştırır
    +------------------------------+
                  |
     +------------+------------+--------------+
     v            v            v              v
  cevap       dayanak      karşı taraf     kararlar
  üretilir    maddeler     maddeleri       (yerel + canlı)
```

Ortalama süre **6-19 saniye**.

### İkinci adım: dört ayrı yoldan aramak

Tek bir arama yöntemi her soruda çalışmaz, o yüzden dördü birden
kullanılıp sonuçları birleştiriliyor:

| Yol | Ne yapar | Ne zaman kurtarır |
|---|---|---|
| **Madde numarası** | "TBK 344" gibi doğrudan adresi yakalar | Avukat maddeyi zaten biliyorsa |
| **Anlam** | Soruyla maddeyi *anlamca* eşleştirir | Kullanıcı hukuki terimi bilmiyorsa |
| **Kelime** | Birebir kelime eşleşmesi arar | Özel bir terim geçiyorsa ("ecrimisil") |
| **Sorunun kendi hâli** | Ham soruyu da ayrıca arar | Çeviri sırasında konu düşerse |

Dördü de kendi listesini verir; bir madde birden çok listede üst
sıralardaysa yukarı çıkar.

### Üçüncü adım: eleme

İlk üç adımdan ~50 aday çıkar. Bunları ikinci bir yapay zekâ modeli
tek tek okur ve "bu madde bu soruya gerçekten cevap veriyor mu" diye
puanlar. En iyi 10'u gösterilir.

Neden ayrı bir adım: ilk arama hızlıdır ama kabadır — konuyla
yüzeysel örtüşen maddeleri de getirir. İkinci model yavaştır ama
isabetlidir; bu yüzden 275 bin maddeye değil, yalnızca ilk aramanın
getirdiği 50 adaya uygulanır.

### Birinci adım neden var

Avukat ile kanun aynı kelimeleri kullanmaz:

```
avukat yazar : "işten çıkarıldım tazminat alabilir miyim"
kanun yazar  : "işveren, iş sözleşmesini feshederken ..."
```

Soruyu olduğu gibi aratmak, iki farklı dil arasında benzerlik aramak
demek. Bu yüzden sistem önce modele **"bu sorunun cevabını içerecek
kanun maddesi nasıl yazılırdı"** diye sorar. Model kısa, uydurma bir
hüküm cümlesi yazar; arama o cümleyle yapılır.

Uydurulan cümle **kullanıcıya asla gösterilmez** — yalnızca arama
sorgusudur. Cevap yine gerçek madde metinlerinden üretilir.

Ölçüldü (34 soruluk set):

| Yöntem | Doğru madde 1. sırada |
|---|---|
| Soruyu doğrudan aratmak | 23/34 |
| Önce kanun diline çevirmek | 32/34 |

Kısaca: **soruyu, cevabın yazıldığı dile çevirip öyle arıyoruz.**

---

## 2. Veri nereden geliyor

### Mevzuat — indirildi, diskte

`mevzuat.gov.tr` üzerinden çekildi ve maddelere ayrıştırıldı.

| Tür | Adet |
|---|---|
| Kanun | 916 |
| Kurum ve Kuruluş Yönetmeliği | 5.049 |
| Tebliğ | 4.471 |
| Cumhurbaşkanlığı Yönetmeliği | 3.655 |
| Yönetmelik | 178 |
| Cumhurbaşkanlığı Kararnamesi | 107 |
| Tüzük | 63 |
| **Katalog toplamı** | **14.439** |

Bunlardan **275.192 madde** çıkarıldı ve aranabilir hale getirildi. Kanunların
%99,3'ü tam — eksik 6 tanesi 1920'lerden kalma nizamnameler.
Yönetmelik ve tüzükler %100.

**Neden indirildi:** Kanun sayısı belli ve sonlu. Ayrıca
mevzuat.gov.tr'de anlam araması yok; site birebir metin eşleştirir,
"kiracımı nasıl çıkarırım" yazınca hiçbir şey bulmaz. Maddeye bölmek,
mülga olanları ayıklamak ve atıfları çıkarmak da ancak tüm metin
elimizdeyken mümkün.

### İçtihat — çoğu canlı, internetten

| Kaynak | Durum |
|---|---|
| Yargıtay (canlı) | `karararama.yargitay.gov.tr` — sınırsız |
| Danıştay (canlı) | `karararama.danistay.gov.tr` — sınırsız |
| Yargıtay (yerel arşiv) | 7.566 karar / 30.828 parça |
| Danıştay (yerel arşiv) | 40 karar |

**Neden indirilmedi:** Yargıtay'da milyonlarca karar var, indirmekle
bitmez. Onun yerine soru sorulduğunda canlı aranıyor.

### Atıf grafiği — türetildi

Kanun metinleri ayrıştırılarak **105.937 madde-madde bağlantısı**
çıkarıldı; her birinin türü de belirlendi:

```
istisnası -> TBK m.138  III. Aşırı ifa güçlüğü
   "Ancak, bu Kanunun, 'Aşırı ifa güçlüğü' başlıklı 138 inci
    maddesi hükmü saklıdır."
```

Ayrıca **1.406 madde** için "bu maddeyi hangi kararlar yorumlamış"
zinciri var.

---

## 3. Sitede ne var

### Cevap

Soru ekranda kalır, altında cevap. Cevabın altındaki yeşil şerit
**kaynak doğrulaması**: cevaptaki her madde numarası ve sayı, gerçek
madde metniyle karşılaştırılır. Eşleşmezse cevap gösterilmez.

Sistem külliyatta karşılık bulamazsa **uydurmaz**, "dayanak bulamadım"
der.

### Olayı anlatırsanız: "Sorunuzu netleştirelim"

Avukat somut bir dosyayla gelir ve soruyu **olguyla** yazar. Ölçüldü —
aynı mesele dört ayrı biçimde sorulduğunda, beş hukuk alanında:

| Nasıl yazıldı | Doğru madde 1. sırada |
|---|---|
| Olay anlatımı (uzun, olgulu) | 1/5 |
| Doğal soru cümlesi | 4/5 |
| Hukuki kavram (kısa) | 5/5 |

Yani sistem, avukatın **en doğal yazma biçiminde** en zayıf. Ama
avukattan "kavram gibi yaz" diye beklemek de doğru değil; o ne
istediğini bilir, nasıl ifade edeceğini bilmez.

Bu yüzden sistem **tahmin etmiyor, soruyor.** Olay anlatımı algılanınca
mesele başlıklarına çevriliyor ve kullanıcı hangisini sorduğunu
seçiyor:

```
yazdığınız:
  "Belediye arazimi imar planı değişikliği yaparak yeşil alana
   çevirdi (kamulaştırdı), bu idari işlemin iptali ve yürütmeyi
   durdurma alabilir miyim?"

Sorunuzu netleştirelim
  - imar planı değişikliğiyle taşınmazın yeşil alana alınması
    suretiyle mülkiyet hakkına müdahale edilmesi
  - idari işlemin uygulanması halinde telafisi güç zararlar
    doğacağı gerekçesiyle yürütmenin durdurulması kararı verilmesi
  - imar planı değişikliği işleminin iptali davası açılması ve
    hukuka aykırılık denetimi
  - Hiçbiri — olayı olduğu gibi ara
```

Seçtiğiniz başlıkla aranıyor. Başlıklar külliyata yakınlığına göre
sıralanıyor: karşılığı olmayan başlık üste çıkmıyor.

**"Hiçbiri" her zaman duruyor** — sistem yanlış anlamışsa avukat onu
aşabilmeli.

### Dört sekme

| Sekme | Ne var |
|---|---|
| **Dayanak maddeler** | Sorunun cevabını içeren maddeler, kanuna göre gruplu |
| **Karşı tarafın gözünden** | Soru karşı taraf adına yeniden kurulup ayrıca aranır |
| **Mahkeme kararları** | Yargıtay kararları + "Daha fazla karar getir" |
| **Dosyam** | Topladıkların |

Madde satırında numara, başlık ve **gövdenin ilk cümlesi** görünür.
Bu son kısım önemli: TCK'da "Etkin pişmanlık" başlıklı 11 madde var,
başlık tek başına ayırt etmiyor.

Maddeye tıklayınca tam metin açılır; soruyla en ilgili cümle
**sarıyla işaretlenir**. Emin değilse işaretlemez — yanlış cümleyi
işaretlemek hiç işaretlememekten kötüdür.

Açılan maddenin altında **bağlantılı maddeler** de görünür: bu maddeye
gönderme yapanlar, bu maddenin istisnası olanlar, yaptırımını
düzenleyenler.

### Karşı tarafın gözünden

```
sen sorarsın : "işten çıkarıldım tazminat alabilir miyim"
sistem arar  : "işverenin haklı nedenle fesih sebepleri"
```

Tavsiye vermez, zayıf nokta söylemez, "şu argümanı kullan" demez.
Yalnızca "bu maddeler de var" der. Çıkarım avukatın.

### Dosyalar (sol panel)

İlk soruyu sorunca dosya kendiliğinden açılır, adını sorudan alır
(çift tıklayarak değiştirilir).

```
yıldız işareti         maddeyi/kararı dosyaya at
geçmiş soru            tıkla, kayıtlı cevap ANINDA gelsin
Bilgisayara kaydet     .aibars.json dosyası indir
Aç                     o dosyayı geri yükle
Metin olarak kopyala   dilekçeye yapıştırılacak düz metin
```

Her şey **tarayıcıda** durur, sunucuya gitmez. Diskteki `.json` avukatın
kendi klasöründe, dava dosyasının yanında durur; yedeklenir,
e-postayla gönderilir, başka makinede açılır.

---

## 4. Yerel arşiv mi, canlı Yargıtay mı

İlk cevapta **3 karar yerel arşivden** gelir — ağ isteği yok, hızlı.
Yerelde yeterli karar yoksa canlı Yargıtay'a çıkılır.
**"Daha fazla karar getir"** düğmesi her zaman canlıya gider ve 12
karar daha çeker.

İkisi de gerektiği ölçüldü:

| Soru | Yerel | Canlı |
|---|---|---|
| işçi kıdem tazminatını hangi hallerde alamaz | **0,98** | 0,74 |
| kiracı iki haklı ihtar nedeniyle tahliye | 0,99 | 0,99 |
| marka hükümsüzlüğü davasını kim açabilir | 0,10 | **0,95** |
| patent hakkına tecavüzde ne talep edilebilir | 0,01 | **0,95** |

*(eleme modelinin verdiği alaka puanı — 1'e yakın olması
"bu karar bu soruya cevap veriyor" demek)*

İndirilmiş alanlarda (iş, kira) yerel arşiv daha iyi; hiç
indirilmemiş alanlarda (marka, patent) yerel fiilen sıfır. Biri
diğerinin yerine geçmiyor.

Canlı arama şöyle çalışır — Yargıtay'ın araması **anlam bilmez**, o
yüzden soru önce hukuki terime çevrilir:

```
"babam ölmeden önce tapuyu kardeşime devretmiş,
 mirastan pay alabilir miyim"
            |  terime çevrilir
            v
      "muris muvazaası"
            |  Yargıtay'da aranır
            v
   gelen kararlar bizim eleme modelimizle sıralanır
```

### Hangi mahkemede aranacağı

Türkiye'de yargı ikiye ayrılıyor ve iki arşiv **ayrı sitelerde**:

```
YARGITAY   kişiler arası uyuşmazlıklar + bütün ceza davaları
           boşanma, miras, kira, iş, ticaret, tazminat, suç

DANIŞTAY   kişi ile DEVLET arasındaki uyuşmazlıklar
           memur, disiplin, atama, vergi, imar, kamulaştırma,
           ruhsat, ihale, öğrenci işleri
```

Yanlış arşivde aramak boş sonuç demek: memur disiplin cezası
Yargıtay'da yoktur. Bu yüzden soru terime çevrilirken **hangi
mahkemede aranacağı da aynı istemde soruluyor** — ayrı bir çağrı
değil, ek gecikme yok.

```
"memura verilen kademe ilerlemesinin durdurulması cezası"
        → disiplin cezasının iptali | DANIŞTAY

"kiracı iki kez ihtar aldı, tahliye edebilir miyim"
        → iki haklı ihtar nedeniyle tahliye | YARGITAY
```

Bu adım atlanırsa Yargıtay kelimeleri OR'layıp alakasız karar getirir.
Ölçüldü: doğal cümleyle arandığında "kadastro öncesi tapu iptali"
kararları geliyordu — konu komşu ama dava başka.

---

## 5. Kullanılan modeller

| İş | Model | Nerede çalışıyor |
|---|---|---|
| Anlam eşleştirme | Qwen3-Embedding-0.6B | Ekran kartında (RTX 3050, 4 GB) |
| Aday eleme | bge-reranker-v2-m3 | Ekran kartında |
| Cevap yazma | Gemini Flash Lite | Google |
| Soruyu çevirme | Gemini Flash Lite | Google |

**Maliyet:** soru başına Google'a 4 istek gidiyor, **0,10 TL** tutuyor.
Günde 20 soru soran bir avukat için ayda ~45 lira.

Kod tarafında **günlük 1 dolarlık sert tavan** var; aşılırsa istek
reddedilir. Tavan istek sayısına değil **paraya** bakar — bir çağrının
maliyeti 100 kat değişiyor (kısa bir terim üretmek ile 10 maddelik
bir cevap yazmak arasında bu kadar fark var), bu yüzden istek saymak
parayı sınırlamıyor.

---

## 6. Bilinen sınırlar

- **Danıştay kararları Yargıtay'a göre daha zayıf eşleşiyor.** Karar
  metni uzun bir usul başlığıyla başlıyor ve içindeki isimler zaten
  "..." ile anonimleştirilmiş; eleme modeli özü geç görüyor.
- **İstinaf (Bölge Adliye Mahkemesi) kararları yok.**
- **Bazı sorularda ilgisiz karar geliyor.** Yerel arşiv soruyla
  yüzeysel örtüşen kararı seçebiliyor; eleme modeli birden çok karara
  tam puan verdiğinde aralarında ayrım yapamıyor.
- **Soruyu kanun diline çevirirken konu düşebiliyor.** "Uyuşturucu
  ticaretinde etkin pişmanlık" sorusunda üretilen cümlede
  "uyuşturucu" geçmedi; TCK'da "Etkin pişmanlık" başlıklı 11 madde
  olduğu için doğrusu kayboldu. Ham soruyu da ayrıca aratmak bunu
  düzeltti (kapsama 33/34'ten 34/34'e çıktı).
- **Vurgulama bazen fazla geniş.** Uzun maddede neredeyse tüm metni
  işaretleyebiliyor; o zaman işaretlemenin anlamı kalmıyor.
- **Kayıtlı cevaplarda karar metinleri kırpık** (4.000 karakter) ve
  mevzuat o günden beri değişmiş olabilir.
- **Hiçbir gerçek avukat henüz kullanmadı.** En büyük eksik bu.

---

## 7. Çalıştırma

**Gereken dört adım:**

```bash
python cli.py katalog     # mevzuat listesini çek
python cli.py cek         # metinleri indir, maddelere ayır
python cli.py indeksle    # aranabilir hale getir
python server.py          # siteyi aç
```

Bu kadarı yeterli. Kararlar zaten Yargıtay'dan canlı geliyor.

**İsteğe bağlı — sistemi zenginleştirir:**

```bash
python cli.py atif-grafi       # "bu madde şunun istisnası" bağlantıları
python cli.py ictihat          # kararları diske indir (hız için)
python cli.py karar-indeksle   # indirilen kararları aranabilir yap
python zincir_kur.py           # hangi karar hangi maddeyi yorumlamış
python cli.py canli-devral     # canlı gelenleri kalıcı arşive kat
```

Kararları indirmek **zorunlu değil**; yalnızca sık sorulan konularda
cevabı hızlandırır.

**260 test** koda eşlik ediyor:

```bash
python -m pytest tests/ -q
```

---

*Aibars genel bilgi verir, hukuki görüş yerine geçmez. Cevaplar
yalnızca resmî mevzuat metinlerine ve Yargıtay kararlarına dayanır. Karar dayanağı yapmadan önce bir avukata danışın.*
