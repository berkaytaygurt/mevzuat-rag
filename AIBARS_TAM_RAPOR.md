# Aibars

Türk mevzuatı ve içtihadı üzerinde çalışan bir hukuk arama asistanı.
Avukat kendi diliyle bir soru yazar; sistem ilgili kanun maddelerini,
karşı tarafın dayanabileceği maddeleri ve Yargıtay kararlarını
kaynağıyla birlikte getirir.

Bu belge sistemin **son halini** anlatır: veri nereden geliyor, arama
nasıl çalışıyor, sitede ne var.

---

## 1. Bir soru sorulduğunda ne oluyor

```
         avukat bir soru yazar
                  |
                  v
    +------------------------------+
    | 1. Soru kanun diline çevrilir|   HyDE - soruyu cevaplayacak
    |                              |   varsayımsal bir hüküm yazılır,
    |                              |   arama onunla yapılır
    +------------------------------+
                  |
                  v
    +------------------------------+
    | 2. Dört ayrı sinyalle aranır |   - madde numarası ("TBK 344")
    |    ve sonuçlar birleştirilir |   - anlam (vektör)
    |                              |   - kelime (BM25)
    |                              |   - ham sorunun kendisi
    +------------------------------+
                  |
                  v
    +------------------------------+
    | 3. En iyi 50 aday yeniden    |   cross-encoder her adayı
    |    sıralanır                 |   soruyla tek tek karşılaştırır
    +------------------------------+
                  |
     +------------+------------+--------------+
     v            v            v              v
  cevap       dayanak      karşı taraf     kararlar
  üretilir    maddeler     maddeleri       (yerel + canlı)
```

Ortalama süre **6-19 saniye**.

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

Bunlardan **275.192 madde** çıkarıldı ve vektörlendi. Kanunların
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
| Yargıtay (yerel arşiv) | 7.566 karar / 30.828 parça |
| Danıştay | 40 karar — CAPTCHA nedeniyle durduruldu |

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

*(ham cross-encoder alaka puanı)*

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
   gelen kararlar bizim reranker'ımızla sıralanır
```

Bu adım atlanırsa Yargıtay kelimeleri OR'layıp alakasız karar getirir.
Ölçüldü: doğal cümleyle arandığında "kadastro öncesi tapu iptali"
kararları geliyordu — konu komşu ama dava başka.

---

## 5. Kullanılan modeller

| İş | Model | Nerede çalışıyor |
|---|---|---|
| Gömme (anlam) | Qwen3-Embedding-0.6B | Yerel GPU (RTX 3050, 4 GB) |
| Yeniden sıralama | BAAI/bge-reranker-v2-m3 | Yerel GPU |
| Cevap üretimi | Gemini Flash Lite | Google API |
| Terim / HyDE üretimi | Gemini Flash Lite | Google API |

**Maliyet:** soru başına 4 Gemini çağrısı, ~6.000 token, **0,10 TL**.
Günde 20 soru soran bir avukat için ayda ~45 lira.

Kod tarafında **günlük 1 dolarlık sert tavan** var; aşılırsa istek
reddedilir. Tavan istek sayısına değil **paraya** bakar — bir çağrının
maliyeti 100 kat değişiyor (terim çıkarma ~200 token, cevap üretme
~20.000 token), bu yüzden istek saymak parayı sınırlamıyor.

---

## 6. Bilinen sınırlar

- **Danıştay boş.** İdari yargı (memur, vergi, imar) kapsanmıyor;
  CAPTCHA çıktığı için çekim 40 kararda durduruldu. Bot denetimi
  aşılmıyor.
- **İstinaf (Bölge Adliye Mahkemesi) kararları yok.**
- **Bazı sorularda ilgisiz karar geliyor.** Yerel arşiv soruyla
  yüzeysel örtüşen kararı seçebiliyor; cross-encoder puanları
  doyduğunda (0,999) ayırt edemiyor.
- **HyDE bazen konuyu düşürüyor.** Aynı başlıklı çok madde olan
  yerlerde doğru madde kaybolabiliyor. Üç çözüm denendi, ikisi
  ölçümde geriletti; üçüncüsü (ham soruyu ayrı sinyal olarak eklemek)
  alındı ve kapsama 33/34'ten 34/34'e çıktı.
- **Vurgulama bazen fazla geniş.** Uzun maddede neredeyse tüm metni
  işaretleyebiliyor; o zaman işaretlemenin anlamı kalmıyor.
- **Kayıtlı cevaplarda karar metinleri kırpık** (4.000 karakter) ve
  mevzuat o günden beri değişmiş olabilir.
- **Hiçbir gerçek avukat henüz kullanmadı.** En büyük eksik bu.

---

## 7. Çalıştırma

```bash
python cli.py katalog          # mevzuat listesini çek
python cli.py cek              # metinleri indir, maddelere ayır
python cli.py indeksle         # GPU'da vektörle, BM25 kur
python cli.py atif-grafi       # madde-madde atıfları çıkar
python cli.py ictihat          # Yargıtay kararı indir (isteğe bağlı)
python cli.py karar-indeksle   # kararları ayrı indekse yaz
python zincir_kur.py           # hangi karar hangi maddeyi yorumlamış
python server.py               # siteyi aç
```

Canlı gelen kararları kalıcı arşive katmak için:

```bash
python cli.py canli-devral
python cli.py karar-indeksle
```

**260 test** koda eşlik ediyor:

```bash
python -m pytest tests/ -q
```

---

*Aibars genel bilgi verir, hukuki görüş yerine geçmez. Cevaplar
yalnızca indekslenmiş mevzuat metinlerine ve Yargıtay kararlarına
dayanır. Karar dayanağı yapmadan önce bir avukata danışın.*
