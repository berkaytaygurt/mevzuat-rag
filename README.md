# mevzuat-rag

Türk mevzuatı üzerinde çalışan, **madde bazlı** yerel bir RAG sistemi. Mevzuat
metinleri `mevzuat.gov.tr`'den çekilir, her madde ayrı bir parça olarak yerel
GPU'da vektöre çevrilir, sorular yalnızca getirilen maddelere dayanarak
cevaplanır.

> Bu araç genel bilgi verir, **hukuki görüş yerine geçmez**. Çıktıyı bir
> avukata danışmadan karar dayanağı yapmayın.

## Ne işe yarıyor — ölçülmüş sonuç

Asıl soru: bu sistemi kurmak yerine doğrudan bir dil modeline sorsak ne olur?
İki ayrı testle ölçüldü.

**Ünlü kanunlarda fark yok.** 52 gerçek iş hukuku sorusunda çıplak Gemini ile
başabaş. 4857 sayılı Kanun internette binlerce kez yazılmış; model zaten
biliyor.

**Bilinmeyen mevzuatta fark büyük.** Tebliğ ve kurum yönetmeliklerinden
seçilen, cevabı somut bir sayı olan 50 soruda:

| | doğru |
|---|---|
| çıplak Gemini | %57 |
| **Aibars** | **%91** |

Gemini'nin yanlışları uydurma: doğrusu 3 iken 4, doğrusu 50 iken "%40 ve %60",
doğrusu 17 iken 9 — ve hepsinde tereddütsüz bir tonla.

Aynı soruların ilki 10'u Claude'a da soruldu: **2/10**.

Kısacası: *bildiğin kanunları sorma, bilmediklerini sor.* Değer modelde değil,
doğru metni bulup modele vermekte.

Ayrıntılı ölçümler ve yöntemin sınırları için `AIBARS_TAM_RAPOR.md`.

## Neden fine-tuning değil

Bir modele mevzuatı fine-tuning ile öğretmek üç sebeple yanlış tercih:

- Model madde numarası ve süre uydurmaya başlar; kullanıcı bunu doğru sanar
- Kanun değiştiğinde yeniden eğitim gerekir
- "Bu cevap hangi maddeden geldi?" sorusuna cevap veremezsiniz

RAG'de metin veritabanında durur, model sadece önüne konan maddeyi okur.
Kaynak gösterilebilir, mevzuat değişince tek komutla güncellenir.

## Mimari

```
mevzuat.gov.tr
   │  POST /anasayfa/MevzuatDatatable   → mevzuat listesi (916 kanun)
   │  GET  /MevzuatMetin/{tur}.{tertip}.{no}.pdf → tam metin
   ▼
scraper/parser.py → madde bazlı JSON (başlık, bölüm, mülga durumu, değişiklikler)
   ▼
core/embedder.py  → Qwen3-Embedding-0.6B, yerel GPU (fp16)
   ▼
core/store.py     → Qdrant (gömülü mod) + metadata indeksi
   ▼
core/retrieve.py  → hibrit arama: madde no + vektör + BM25, RRF ile birleştirme
   ▼
core/generate.py  → Qwen2.5-3B (yerel) veya Gemini Flash
```

## Tasarım kararları

**Madde bazlı chunking.** Hukuk metni zaten maddelere bölünmüş. Sabit karakter
sayısıyla kesmek madde bütünlüğünü bozar ve cevabın dayanağını kaybettirir.
Her madde bir parça; embedding'e kanun adı, bölüm ve madde başlığı da eklenir
ki "yıllık izin" sorgusu, ifade gövdede geçmese bile eşleşebilsin.

**Bellek sınırı ve kırpma.** Embedding 4 GB VRAM'de çalışır. `batch=8`,
`max_seq_length=512` ayarı 2,19 GB tepe kullanımla güvenli. Bu sınırlar
aşıldığında Windows GPU belleğini sistem RAM'ine takas eder ve iş hata vermeden
280 kat yavaşlar: `batch=16, seq=1024` denemesinde batch süresi 0,9 saniyeden
255 saniyeye çıktı, tahmini bitiş 30 dakikadan 149 saate fırladı. Maddelerin
%10'u 512 token'da kırpılır; kırpılan kısım kuyruktur (başlık ve kanun adı
metnin başındadır) ve BM25 tam metni indekslemeye devam eder.

**Kaynak olarak PDF, HTML değil.** Sitenin iframe HTML'i uzun kanunları
sessizce kesiyor:

| Kanun | iframe HTML | PDF | Gerçek |
|---|---|---|---|
| Türk Medeni Kanunu | 425 madde | **1030** | 1030 |
| Türk Borçlar Kanunu | 481 | **649** | 649 |
| Hukuk Muhakemeleri K. | 358 | **458** | 452+ek |

HTML ayrıca metnin %6.7'sinde çift-encode bozulması taşıyor (`Ã¶`), PDF'te bu
sorun yok. HTML yolu yedek olarak duruyor.

**PDF çıkarıcı olarak PyMuPDF.** `pypdf` bu belgelerde kelime ortasına boşluk
sokuyor (`"s özleşmenin"`, `"aş ılanması v e nak li"`) — TMK'de her bin
kelimede 12 bozuk token. PyMuPDF aynı belgede bu oranı 1.2'ye düşürüyor ve
kalanlar meşru "o" zamiri. Bozuk token BM25 eşleşmesini doğrudan kaybettirir.

**İki aşamalı arama.** Birinci aşama hızlı aday toplar (vektör + BM25 + madde
numarası); ikinci aşama bir cross-encoder ile bu adayları yeniden sıralar.
Aradaki fark, sorunun ve madde metninin birlikte okunması: birinci aşama ikisini
ayrı ayrı vektöre çevirip kaba benzerliğe bakar, ikinci aşama "bu madde bu
soruya cevap veriyor mu" diye değerlendirir. Cross-encoder yavaş olduğu için
tüm külliyata değil, yalnızca ilk aşamanın getirdiği 12 adaya uygulanır.
12 aday / 256 token, 25 aday / 512 token ile aynı isabeti veriyor (MRR 0,753 vs
0,740) ama dört kat az hesap yapıyor.

**Hibrit arama.** Kullanıcı "TBK 6. madde" diye sorar; anlamsal benzerlik sayı
eşleştirmede zayıftır ve "6" ile "60" farkını kaçıran cevap hukuken tamamen
yanlıştır. Üç yol birlikte çalışır: doğrudan madde numarası eşleşmesi (en
yüksek ağırlık), vektör benzerliği, BM25.

**Türkçe karakter katlama.** Kullanıcılar sorgularını çoğunlukla Türkçe
karakter kullanmadan yazar. Katlama olmadan BM25 `kisisel` ile `kişisel`i ayrı
token sayıyordu ve birebir başlık eşleşmesi olan madde hiç getirilemiyordu:

| Sorgu | Katlama öncesi | Sonrası |
|---|---|---|
| `kisisel verilerin islenmesi sartlari` | ilk 3'te yok | **1. sıra** |

Başlık, BM25 metninde üç kez tekrarlanır; uzun gövde metni başlığı seyreltip
birebir eşleşmeyi alt sıraya itiyordu.

**Kök bulma (stemming) eklenmedi.** Türkçe sondan eklemeli olduğu için stemming
cazip görünüyor, ancak Snowball'un Türkçe kök bulucusu bu külliyatta güvenilmez:
`yaş/yaşı/yaşını` doğru birleşiyor ama `izin → "iz"`, `izinler → "izin"` diye
parçalayarak hâlihazırda doğru çalışan sorguları bozuyor. Net etkisi negatif.

**Mülga ile kısmi mülga ayrımı.** Yürürlükten kalkma işareti metnin başındaysa
madde tamamen mülgadır; gövdenin içindeyse yalnızca bir fıkrası kaldırılmıştır
ve madde yürürlüktedir (ör. KVKK m.6: 2. fıkra 2024'te mülga, madde yürürlükte).
Ayrım yapılmadığında işaretli 54 maddenin 20'si yanlışlıkla yürürlükten kalkmış
sayılıyor ve varsayılan aramadan tamamen düşüyordu.

**Mülga takibi.** Yürürlükten kalkmış bir maddeyi güncelmiş gibi sunmak bu
projedeki en tehlikeli hata türü. Mülga durumu metadata'da tutulur, varsayılan
olarak aramadan hariç tutulur ve arayüzde işaretlenir.

**TLS.** `mevzuat.gov.tr` ara sertifikayı göndermiyor. `verify=False` yerine
DigiCert ara sertifikası `certs/` altında bundle'lanır; doğrulama tam kalır.

## Kurulum

```bash
python -m venv .venv
```

```bash
.venv\Scripts\pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu126
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

CUDA'yı doğrulayın:

```bash
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"
```

Ayarlar için `.env.example` dosyasını `.env` olarak kopyalayın.

### Cevap üretimi sağlayıcısı

`.env` içindeki `PROVIDER` değerini değiştirerek seçilir:

- `PROVIDER=local` — GGUF model, tamamen çevrimdışı, ücretsiz. 4 GB VRAM için
  `Qwen2.5-3B-Instruct-Q4_K_M` uygun:

  ```bash
  .venv\Scripts\pip install llama-cpp-python==0.3.4 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
  ```

  Model dosyası (~1.9 GB):

  ```bash
  .venv\Scripts\python -c "from huggingface_hub import hf_hub_download; hf_hub_download('bartowski/Qwen2.5-3B-Instruct-GGUF','Qwen2.5-3B-Instruct-Q4_K_M.gguf',local_dir='models')"
  ```

  Embedding modeli zaten VRAM'de olduğu için sohbet modelinin tüm katmanları
  4 GB'a sığmayabilir. Kod bunu kendisi yönetir: önce hepsini GPU'ya koymayı
  dener, bellek yetmezse 20, 10, 0 katmanla tekrar dener. Katman azaldıkça
  yavaşlar ama çalışır.
- `PROVIDER=gemini` — `GEMINI_API_KEY` gerekir. Daha iyi Türkçe sentez ve geniş
  bağlam, ancak **sorulan maddeler Google'a gönderilir**.

Embedding her iki durumda da yerel GPU'da çalışır.

## Kullanım

Pilot (6 temel kanun: İş K., TBK, TMK, TCK, HMK, KVKK):

```bash
python cli.py cek --pilot
```

Tüm kanunlar (~916 mevzuat, 1.5 sn gecikmeyle yaklaşık 25 dakika):

```bash
python cli.py katalog --tur 1
```

```bash
python cli.py cek
```

İndeksleme (GPU):

```bash
python cli.py indeksle
```

Soru sorma:

```bash
python cli.py sor "yillik ucretli izin suresi kac gundur"
```

Arayüz (**Aibars**):

```bash
.venv\Scripts\python server.py
```

Sonra tarayıcıda `http://localhost:8000`. Sunucu yalnızca `localhost`'ta
dinler, dışarıya hiçbir şey göndermez, anahtar gerektirmez — tarayıcıdaki
sayfanın Python koduna erişmesi için gereken köprüden ibarettir.

Streamlit arayüzü de duruyor (`streamlit run app.py`) ama asıl arayüz Aibars.

## Testler

```bash
python -m pytest tests/ -q
```

Testler ağ bağlantısı gerektirmez; önbellekteki PDF'leri kullanır, yoksa
atlanır. Her test geliştirme sırasında gerçekten karşılaşılan bir hataya
karşılık gelir (uzun kanunun kesilmesi, liste öğesinin başlık sanılması,
`chunk_id` çakışması, değişiklik tablosunun metne sızması).

## Üretilen çıktının doğrulanması

Yerel 3B model, önüne konan maddeye rağmen **sayı ve kaynak uydurabiliyor**.
Gözlenen iki örnek:

- Kanun "ondört / yirmi / yirmialtı gün" derken model "14 gün ... 24 gün" yazdı
- Gerçek kaynak TMK m.170 iken model "(İşçiye Kolektif Haklar Kanunu m.12)"
  diye var olmayan bir kanun gösterdi

Hukukta uydurulmuş bir süre, yanlış cevaptan daha zararlıdır: kullanıcı rakamı
doğru sanıp dayanak yapar. Bu yüzden cevap üretildikten sonra iki denetimden
geçer:

- **Atıf denetimi** — cevaptaki her `(Kanun m.X)` gösterimi, getirilen
  maddelerle karşılaştırılır
- **Sayı denetimi** — cevaptaki her rakamın kaynak metinde geçtiği doğrulanır.
  Mevzuat sayıları yazıyla yazdığı ("ondört"), model rakamla cevapladığı ("14")
  için yazı→rakam çevrimi yapılır

Eşleşmeyen varsa cevabın altına `⚠ Doğrulanmalı` uyarısı eklenir. Denetimler
hatayı **önlemez, görünür kılar**.

## Ölçüm

Arama isabeti, cevabı önceden bilinen 34 soruluk bir setle ölçülür
(`tests/olcum_seti.py`). Setteki her cevabın külliyatta gerçekten var olduğu
doğrulandı.

```bash
python olcum.py                    # temel
python olcum.py --rerank           # yeniden sıralama açık
python olcum.py --rerank --ascii   # Türkçe karakter kullanmadan
```

Eklenen her katmanın ölçülen katkısı (ASCII sorgular):

| Aşama | 1. sırada | MRR | Süre/soru |
|---|---|---|---|
| Temel (hibrit arama) | 12/34 (%35) | 0,538 | 0,70 sn |
| + yeniden sıralama | 18/34 (%53) | 0,645 | 1,04 sn |
| + yazım düzeltme | 20/34 (%59) | 0,701 | 1,04 sn |
| **+ puan harmanlama** | **23/34 (%68)** | **0,736** | **1,68 sn** |
| (+ sorgu genişletme) | 25/34 (%74) | 0,766 | 30,8 sn |

MRR (ortalama karşılıklı sıra) tek başına en bilgilendirici olan; "ilk 5'te
var" ifadesi 1. sırada olmakla 5. sırada olmak arasındaki farkı gizler.

Yeniden sıralama her iki yazım biçiminde de kazandırıyor (%20-23) ve sorgu
başına yalnızca 0,34 saniye ekliyor (0,70 → 1,04 sn, model yükleme hariç).

## Külliyat eksikleri ve nedenleri (31.08.2026'da çözüldü)

Külliyatın %28'i (4.099 belge) indekse hiç girmemişti. İki ayrı sessiz hata:

**1. PDF adresi tür bazında farklı.** Adres `/MevzuatMetin/{tur}.{tertip}.{no}.pdf`
kalıbıyla kuruluyordu. Ölçüldü — her türden bir belge indirilerek:

| Tür | Dizin |
|---|---|
| Kanun, CB Kararnamesi, Tüzük, Yönetmelik | yok |
| Tebliğ, Kurum Yönetmeliği, CB Yönetmeliği | `yonetmelik/` |

Alt dizin atlanınca sunucu 404 vermiyor, her seferinde aynı 60.487 baytlık boş
"belge bulunamadı" PDF'ini döndürüyordu. Artık bu boyut tanınıyor
(`MevzuatClient.BOS_PDF_BOYUTU`) ve bilinen dizinler sırayla deneniyor.

**2. Madde başlığı olmayan belgeler atılıyordu.** Tebliğlerin önemli bir kısmı
numaralı madde içermiyor, düz metin olarak yazılıyor. Madde arayan ayrıştırıcı
bunları boş döndürüyor, belge tümüyle kayboluyordu. Artık böyle belgeler
paragraf sınırlarından ~1500 karakterlik parçalara bölünüyor
(`parser._duz_metin_parcalari`, madde numarası `Metin 1`, `Metin 2`, ...).

Bu iki hatanın ikincil bir sonucu daha vardı: PDF alınamayınca kod HTML'e
düşüyordu, HTML ise uzun belgeleri sessizce kesiyor (TMK'da 1030 madde yerine
425 veriyordu). Yani tebliğ ve yönetmeliklerin "başarılı" görünen kısmı da
eksik olabilir. `cek --yenile-tur 7 8 9` bunları PDF'ten yeniden çeker.

**Katalog da eksikti.** Liste isteği 3.000. kayıtta hata veriyordu ve 4 deneme
sonrası vazgeçiliyordu; kalıcı bir sınır sanılmıştı. Deneme sayısı 8'e,
sayfa boyu 50'ye çekilince üç tür de eksiksiz geldi (10.164 → 14.439 belge).

## Madde metinleri kesiliyordu (02.09.2026'da çözüldü)

Bir avukat sorusu bunu ortaya çıkardı: *"işçi 4 yıl 11 ay çalıştı, işveren
devamsızlık nedeniyle savunma almadan feshetti, fesih geçerli mi"*. Sistem
dayanak bulamadı. Beklenen cevap İş Kanunu m.19'du ve madde indekste vardı —
ama **112 karakter** olarak. Maddenin ikinci fıkrası ("Hakkındaki iddialara
karşı savunmasını almadan ... feshedilemez"), yani işe iade davalarının
dayandığı hüküm, külliyatta hiç yoktu. "savunmas" kelimesi 4857 sayılı
Kanun'un tamamında geçmiyordu.

Üç ayrı hata çıktı.

**1. Sayfa altı dipnotu maddeyi kesiyordu.** PDF'te dipnot, maddenin iki
fıkrası *arasına* düşüyor. Ayrıştırıcı dipnot satırını görünce `flush()`
çağırıp maddeyi kapatıyor, sonraki fıkralar `current is None` olduğu için
sessizce çöpe gidiyordu:

```
Madde 19 - İşveren fesih bildirimini yazılı olarak yapmak ve ...
kesin bir şekilde belirtmek zorundadır.
6 18/2/2009 tarihli ve 5838 sayılı Kanunun 32 nci maddesiyle; ...   ← dipnot
Hakkındaki iddialara karşı savunmasını almadan bir işçinin ...      ← kayıp
```

Dipnotlar gövdeden küçük punto ile diziliyor ve ayrım kesin — ölçüldü (4857):
gövde 12,0 punto / 2.024 satır, dipnot 11,0 punto / 117 satır, istisna yok.
Artık `bloklar_pdf` satırların puntosunu PyMuPDF'ten okuyor ve en çok
kullanılan puntonun altındakileri atıyor. Madde kesilmiyor.

**2. Dipnot metni gövdeye sızıyordu.** Eski kod dipnotun yalnızca ilk
satırını tanıyordu; devam satırları madde metnine yapışıyordu:

```
ESKİ: "Bu Kanun hükümlerini Bakanlar Kurulu yürütür 5 Bu maddede geçen
       '...belediyeler...' sözcüğü; Anayasa Mahkemesinin 27/6/1995 tarih ve
       E.1994/90 sayılı kararıyla iptal edilmiştir."
YENİ: "Bu Kanun hükümlerini Bakanlar Kurulu yürütür"
```

**3. `Madde 3/A` diye bir madde yoktu.** Harf eki yakalanmıyordu; harfli
maddeler numarayı kaybedip aynı numaraya düşüyor, çakışma da `3 (2)`, `3 (9)`
diye çözülüyordu — kimsenin arayamayacağı bir ad. 1.740 madde bu durumdaydı.

Ayrıca her maddenin metni bir *sonraki* maddenin başlığıyla bitiyordu
(`"... saklıdır. Fesih bildirimine itiraz ve usulü"`). Başlık satırı hem
başlık olarak alınıp hem gövdeye ekleniyordu. Temizlik korumalı yapıldı:
başlık sezgisi kesin değil (`"... yerine işlenmiştir.)"` de başlık görünüyor)
ve korumasız silmek gerçek metin kaybettiriyordu.

### Ölçülen sonuç

Kanunlar yeniden çekildi (907 belge). Metin hacmi:

| | önce | sonra |
|---|---|---|
| Kanun maddesi | 33.742 | 33.827 |
| Toplam karakter | 21.744.385 | **25.742.496** (%+18,4) |
| Doğru numaralanmış harfli madde | 0 | 472 |
| İş Kanunu m.19 | 112 karakter | 363 karakter |

Aynı 34 soruluk set, aynı ayarlarla iki külliyat üzerinde koşuldu (eski
külliyat ayrı bir indekse kurulup ölçüldü):

| | eski külliyat | yeni külliyat |
|---|---|---|
| 1. sırada | 14/34 (%41) | **23/34 (%68)** |
| ilk 3'te | 20/34 | **26/34** |
| ilk 5'te | 24/34 (%71) | **29/34 (%85)** |
| MRR | 0,524 | **0,748** |

14 soru iyileşti, 3 soru birer sıra geriledi (3→5, 5→6, 5→6). Daha önce hiç
bulunamayan 5 soru artık bulunuyor. Sorunu ortaya çıkaran avukat sorusu m.19'u
4. sırada getiriyor — mesele ayırma kapalıyken.

Regresyon testleri: `tests/test_dipnot.py`.

**Kalan iş:** tebliğ ve yönetmelikler henüz yeniden çekilmedi (10.781 belge);
onların metinlerinde dipnot kirliliği duruyor.

### Artımlı indeksleme

Bu ölçüm ancak indeksleme artımlı hale getirildiği için yapılabildi.
275.891 maddeyi baştan gömmek RTX 3050'de ~6,8 saat sürüyor; oysa bir
ayrıştırıcı düzeltmesi maddelerin küçük bir bölümünü değiştiriyor. Artık
embed metni değişmeyen maddenin vektörü önceki indeksten alınıyor
(`cli._onceki_vektorler`): 252.541 madde yeniden kullanıldı, 23.350 madde
gömüldü, süre **35 dakikaya** indi. Eşleme sıraya değil metnin kendisine
dayanıyor; yanlış eşleme sessizce saçmalatacağı için `tests/test_artimli_indeks.py`
ile sabitlendi. `indeksle --tam` eski davranışı verir.

BM25 adımında iki kusur bu sırada ortaya çıktı ve düzeltildi: `pickle.dump`
275 bin maddede `MemoryError` veriyordu (kayıtların tam kopyasını da
yazdığı için) ve doğrudan hedef dosyaya yazdığı için çökünce `bm25.pkl`
599 MB'tan 69 MB'a düşüp aramanın BM25 yarısını bozuyordu. Artık kayıt
kopyası yazılmıyor (267 MB), yazım atomik ve `cli.py bm25` yalnızca bu adımı
yeniden kurabiliyor.

## Mahkeme kararları

Kararlar **ayrı bir indekste** tutulur (`data/index_karar`). Tek indekste
birleştirilmiyor: kararlar daha uzun ve konuyu daha çok tekrarladığı için
maddeleri sıradan itiyorlar, oysa kullanıcının önce dayanak maddeyi görmesi
gerekiyor. Ayrılık ayrıca çalışan sistemi korur — karar indeksi yoksa ya da
bozuksa mevzuat araması etkilenmez.

    python cli.py ictihat --gecikme 12 --adet 150
    python cli.py karar-indeksle

**Gerekçe ayıklama denendi ve bırakıldı.** Kod, gerekçenin
`GEREĞİ DÜŞÜNÜLDÜ` ifadesiyle başladığını varsayıyordu. 15 gerçek kararda
ölçüldü:

| İşaret | Kaç kararda |
|---|---|
| GEREĞİ GÖRÜŞÜLDÜ | 4/15 |
| GEREKÇE: | 3/15 |
| GEREĞİ DÜŞÜNÜLDÜ | 0/15 |
| DELİLLERİN DEĞERLENDİRİLMESİ | 0/15 |

Kararların çoğunda böyle bir işaret yok; kod sessizce "metnin ikinci yarısını
al" yedeğine düşüyor ve gerekçenin başını kesiyordu. Şimdiki yaklaşım işaret
aramıyor: künye satırları (ölçülerek belirlendi — karar başına ~422 karakter)
atılıyor, kalan metin parçalanıyor. Doğru parçayı arama zaten buluyor.

**Yargıtay WAF'ı.** `karararama.yargitay.gov.tr` F5 BIG-IP ile korunuyor.
5-6 saniye aralıkla ~15 istekten sonra engelliyor; **12 saniye aralıkla
engellemedi**. Bu sınır aşılmaya çalışılmamalı.

## Doğal dilde arama — ölçülen zayıflık

Sistemin en belirgin zayıflığı bu. Aynı bilgiyi soran üç sorgu:

| Sorgu | Doğru maddenin sırası |
|---|---|
| `kıdem tazminatı şartları` | 1 |
| `kıdem tazminatı` | 8 |
| `kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir` | 21 |

Üç ölçüm setinde de aynı eğilim var — sorular ne kadar doğal yazılırsa isabet
o kadar düşüyor:

| Set | Nasıl üretildi | MRR |
|---|---|---|
| El yazımı (34) | elle, cevabı doğrulanarak | 0,725 |
| Yerel model (150) | 3B model, dili çoğu kez bozuk | 0,445 |
| Gemini (40) | doğal Türkçe, günlük dil | 0,250 |

Kullanıcılar üçüncü gruptaki gibi soruyor. Yani gerçek doğruluk 0,72 değil,
ona yakın da değil.

**Denenen: çekirdek sorgu.** Sorgunun soru kalıplarından arındırılmış hâli
(`core.retrieve.cekirdek_sorgu`) ayrı bir sinyal olarak aratılıp RRF ile
birleştiriliyor. LLM gerektirmiyor, maliyeti tek bir ek gömme.

| Ayar | El (34) | Yerel (150) | Gemini (40) |
|---|---|---|---|
| Kapalı | 0,725 | 0,445 | 0,250 |
| Açık | **0,744** | **0,447** | **0,258** |

Kazanç küçük (224 soruda 3 soru) ama üç sette de negatif değil, o yüzden
açık bırakıldı (`CEKIRDEK_SORGU=0` ile kapatılabilir).

İlk sürümde çekirdek, sentetik soruların %100'ünde devreye giriyordu: yalnızca
soru işaretini silmek bile "değişti" sayılıyordu ve ikinci arama birincinin
neredeyse aynısını arayıp RRF'e gürültü ekliyordu. Yerel sette ilk-5 isabetini
85'ten 83'e düşürmüştü. Artık yalnızca gerçek bir soru kelimesi atıldığında
devreye giriyor (%71).

**Uygulanan: sıralayıcının gördüğü metnin uzatılması.** Cross-encoder
maddenin ilk `RERANK_MAX_SEQ` token'ini görüyor. 256 token (~768 karakter)
külliyattaki **58.975 maddeyi (%34)** kesiyordu; başarısız örnekteki madde
(1475 m.14, 2.002 karakter) yalnızca %38'i görülerek sıralanıyordu.

| max_seq | El (34) | Yerel (150) | Gemini (40) | Süre |
|---|---|---|---|---|
| 256 | 0,744 | 0,447 (ilk-5: 85) | 0,258 | 1,21 sn |
| 384 | 0,718 | 0,457 (ilk-5: 85) | 0,261 | 1,35 sn |
| **512** | 0,722 | **0,474 (ilk-5: 89)** | **0,261** | 1,45 sn |

En büyük sette üç değer boyunca tek yönlü artış var; bu, tek bir
karşılaştırmadan güçlü bir kanıt. El setindeki 2 soruluk düşüş o setin
gürültü sınırında (34 soru). Yığın boyutu 12'den 6'ya indirildi — 4 GB
VRAM'de uzun dizi ile 12'lik yığın sığmıyor.

Tek örnekte de doğrulandı: `kıdem tazminatına hak kazanmak için ne kadar
çalışmak gerekir` sorgusunda doğru madde **21. sıradan 6. sıraya** çıktı.
İlk 5'e girmiyor ama modele 10 madde gönderildiği için cevaba dahil oluyor.

**Denenen ve bırakılan: ek/geçici madde cezasını artırmak.** Doğal sorguda
"Geçici 11" gibi maddelerin öne geçtiği görülmüştü. Ceza 0,00 ile 0,05
arasında üç sette de fark yaratmadı (0,724/0,725 — 0,446/0,445 —
0,250/0,250); varsayılan değiştirilmedi.

## Danıştay kararları (03.09.2026)

Külliyatta yalnızca Yargıtay kararı vardı. Memur, disiplin, atama, mobbing
gibi uyuşmazlıklar **idari yargıya** gidiyor ve o kararlar Danıştay'da.
Ölçüldü: *"kadrolu öğretmene mobbing"* sorusunda sistem TBK m.417'yi
getiriyordu — o hüküm işçi içindir, memura doğrudan uygulanmaz.

**Uç Yargıtay'dan farklı.** Danıştay çoğul ve dizi alanlar bekliyor:

```
andKelimeler = ["\"mobbing\""]      ← değer tırnak içinde
orKelimeler, notAndKelimeler, notOrKelimeler
```

Tekil `andKelime` gönderilince sunucu *"Lütfen arama kriterlerini giriniz!"*
diyor. Doğru şekil, sitenin kendi betiğindeki `formData` kurulumu okunarak
bulundu — tahminle değil.

Akış: `POST /arama` (oturumda aramayı kurar) → `POST /aramalist` (liste) →
`GET /getDokuman?id=&arananKelime=` (tam metin).

**CAPTCHA SINIRI.** Sunucu istediği anda captcha isteyebiliyor ve gece
tam olarak bunu yaptı: `metadata.FMTE` içinde `DisplayCaptcha` döndü.
İstemci bu durumda **duruyor** (`CaptchaAcik`); captcha çözülmüyor,
oturum tazeleyip atlatılmıyor. İlk denetimimiz yalnızca sayfa bayrağına
baktığı için bu sinyali kaçırdı ve yedi anahtar sessizce "0 kayıt"
döndü; denetim API mesajını da kapsayacak şekilde düzeltildi.

İlk çekimde 40 mobbing kararı alındı — 2., 12., 8., 5., 10. Daire ve
İdari Dava Daireleri Kurulu. İçerik doğru yeri dolduruyor: 40 kararın
17'sinde "memur", 21'inde "disiplin", 12'sinde 657 sayılı Kanun geçiyor.

Karar metni temizliği iki geçişe çıkarıldı: Danıştay iç HTML'i kaçışlı
gönderiyor ve tek geçişte etiketler metne geri geliyordu.

    python cli.py danistay --adet 150

## Ölçüm günlüğü

Hangi sorgunun yavaş ya da zayıf olduğu ancak gerçek kullanımda görülüyor.
Her `/api/sor` çağrısı için süre, madde sayısı, ilk sonuç, güven puanı ve
cevabın üretilip üretilmediği tek satır JSON olarak yazılabiliyor.

**Varsayılan kapalı.** Kayıt soru metnini de tutuyor; site tünelle dışarı
açıksa başkalarının sorguları da yazılır ve bu, sahibinin bilerek vermesi
gereken bir karar. `METRIK=1` ile açılır, `data/metrik.jsonl` dosyasına
yazar. Yazım hatası cevabı engellemiyor.

## Bilinen sınırlar

**Aday penceresini genişletmek işe yaramıyor.** Ölçüldü: ilk aşama doğru
maddeyi 12 adaylık pencerede %88, 50 adaylıkta %97 oranında havuza sokuyor.
Ama pencereyi genişletmek çıktıyı değiştirmiyor (MRR 0,736 → 0,736). Yani
doğru madde sıralayıcının önüne geliyor, sıralayıcı onu üste çıkarmıyor.
Darboğaz arama değil, sıralama.

**Puan harmanlama.** Cross-encoder puanını tek başına kullanmak, ilk aşamanın
RRF puanını çöpe atmak demek — oysa o puan madde numarası eşleşmesi ve BM25
sinyalini taşıyor. İkisi harmanlanıyor (`RERANK_AGIRLIK`, varsayılan 0,8).
Ağırlık taramasında 0,70–0,95 aralığının tamamı saf cross-encoder'dan
(MRR 0,696) iyi çıktı.

**Sorgu genişletme kapalı.** Sorguyu LLM'e verip hukuk terimleriyle
zenginleştirmek isabeti artırıyor (23/34 → 25/34) ama:

- Gemini ile soru başına 1,68 sn yerine 30,8 sn (ücretsiz katmanın 503'leri)
- Yerel 3B model hızlı ama kullanılamaz çıktı veriyor: `evlenme yaşı kaç`
  sorgusuna `evlenme_yasi, evlilik_yasasi, evlilik_yas_kodu` gibi uydurma
  terimler üretiyor. Hukuk terminolojisi bilgisi gerektiren bir iş bu.
- Aramayı dış servise bağımlı yapıyor

`SORGU_GENISLET=1` ile açılabilir. Daha büyük bir ölçüm setiyle kazancın
gerçek olduğu doğrulanırsa yeniden değerlendirilmeli.

**ASCII sorgular kalıcı olarak daha zayıf.** Türkçe karakter kullanılmadan
yazılan sorgularda MRR 0,753'ten 0,645'e düşüyor. BM25 tarafında karakter
katlama uygulanıyor, cross-encoder girdilerinde de uygulanıyor
(`RERANK_KATLA`), ama aradaki fark tamamen kapanmıyor: aksansız yazımda
kelimeler ayırt ediciliğini kısmen kaybediyor.

**Bazı sorular hâlâ ıskalanıyor.** `ihbar öneli süreleri` ve `işe iade davası
şartları` sorularında doğru madde ilk 5'e giremiyor; ilk aşama bu maddeleri
aday penceresine hiç sokmadığı için yeniden sıralama da kurtaramıyor.

**Yerel 3B model cevap kalitesi için yeterli değil.** Arama katmanı sağlam,
üretim katmanı değil. `PROVIDER=gemini` bu sorunu büyük ölçüde çözer ama
sorulan maddeler Google'a gider.

9 kanun ayrıştırılamadı — hepsi 1920'ler tarihli Osmanlıca metinler
(`Darülaceze Nizamnamesi`, `Rumeli Demiryolları`), farklı madde biçimi
kullanıyorlar.

## Veri kaynağı ve kullanım

Veriler `mevzuat.gov.tr`'den, kimlik doğrulama gerektirmeyen açık uçlardan
alınır. `robots.txt` hiçbir `Disallow` veya `Crawl-delay` içermez; yine de
istekler arasında varsayılan 1.5 saniye beklenir, `User-Agent` içinde iletişim
bilgisi taşınır ve indirilen her belge yerel önbelleğe alınır.

Kanun, yönetmelik ve yargı kararları FSEK m.31 uyarınca telif korumasına tabi
değildir. Abonelik gerektiren ticari hukuk veritabanlarının editoryal içeriği
(şerh, doktrin, çapraz referans) bu kapsamda **değildir** ve bu proje onlara
dokunmaz.

## Dosyalar

| Dosya | Görev |
|---|---|
| `scraper/client.py` | Nazik HTTP istemcisi: TLS bundle, gecikme, geri çekilme, disk önbelleği |
| `scraper/catalog.py` | `MevzuatDatatable` üzerinden mevzuat listesi |
| `scraper/parser.py` | PDF/HTML → madde bazlı yapı |
| `core/embedder.py` | Qwen3-Embedding, sorgu/doküman asimetrisi |
| `core/store.py` | Qdrant gömülü vektör + metadata deposu |
| `core/retrieve.py` | Hibrit arama ve RRF birleştirme |
| `core/reranker.py` | Cross-encoder ile yeniden sıralama ve puan harmanlama |
| `core/yazim.py` | Aksansız sorguları külliyattan çıkarılan sözlükle düzeltme |
| `core/sorgu.py` | Sorgu genişletme (varsayılan kapalı) |
| `tavan_olc.py` | İlk aşamanın tavanını ölçer |
| `olcum.py` | Arama isabeti ölçümü |
| `tests/olcum_seti.py` | 34 soruluk ölçüm seti (cevaplarıyla) |
| `core/generate.py` | Sağlayıcı seçmeli cevap üretimi |
| `cli.py` | `katalog` / `cek` / `indeksle` / `sor` |
| `server.py` | Aibars web sunucusu (yalnızca localhost) |
| `web/aibars.html` | Aibars arayüzü |
| `app.py` | Streamlit arayüzü (alternatif) |
