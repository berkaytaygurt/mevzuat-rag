# Aibars — Tam Rapor

*Türk mevzuatı üzerinde çalışan bir arama ve cevaplama sistemi.
Bu belge projeyi sıfırdan anlatır: ne olduğu, nasıl kurulduğu, hangi
ölçümlerin yapıldığı ve neyin kanıtlandığı. Aleyhte çıkan sonuçlar da
yazıldı.*

---

## 1. Sorun

Bir avukatın mevzuatta bir şey araması gerektiğinde iki seçeneği var:

- **mevzuat.gov.tr** — kelime araması yapar. Soru soramaz, sonuçlar arasında
  hangisinin ilgili olduğunu kendisi bulur.
- **Bir yapay zekâya sormak** — cevap alır ama kaynak göremez, ve model
  bilmediği yerde uydurur.

Ticari çözümler (Lexpera, Kazancı) bu boşluğu dolduruyor, aylık ücretli.

## 2. Aibars ne yapıyor

Soru yazılır. Sistem:

1. 275.806 madde içinde **anlamsal arama** yapar — kelime değil anlam
   eşleştirir. "İşten atıldım param ne olur" ile kıdem tazminatı maddesini
   eşleştirebilir.
2. En ilgili 10 maddeyi bulur.
3. Bu maddelerin **tam metnini** dil modeline verir: *"yalnızca bunlara
   dayanarak cevapla."*
4. Cevabın altında dayanak maddeleri tam metinleriyle ve resmî kaynak
   bağlantısıyla gösterir.

Model kendi hafızasından konuşmuyor; verilen metni okuyup açıklıyor. Bu
yönteme **RAG** (Retrieval-Augmented Generation) deniyor.

**Neden fine-tuning değil:** kanunlar değişir, her değişiklikte yeniden
eğitim gerekir; eğitilmiş model kaynak gösteremez; ezberlediğini yanlış
hatırlayabilir. RAG'de kanun değişince yalnızca indeks güncellenir.

---

## 3. Veri

Kaynak: **mevzuat.gov.tr**, devletin resmî sitesi. Kanun metinleri FSEK
m.31 uyarınca telif korumasında değil.

### Külliyat

| Tür | Sitede | İndekste | Kapsam |
|---|---|---|---|
| Kanun | 916 | 907 | %99 |
| Tüzük | 63 | 63 | %100 |
| Yönetmelik | 178 | 177 | %99 |
| CB Kararnamesi | 107 | 102 | %95 |
| CB Yönetmeliği | 3.653 | 3.003 | %82 |
| Kurum Yönetmeliği | 5.049 | 3.384 | %67 |
| Tebliğ | 4.470 | 2.965 | %66 |
| **Toplam** | **14.436** | **10.601** | **%73** |

**275.806 madde**, 199 milyon karakter (~99.600 sayfa).
Kanun hükmünde kararnameler (8.851 belge) siteden sunulmuyor.

### Mahkeme kararları

Yargıtay'dan **2.890 karar**, tamamı iş hukuku (9., 22., 7. Hukuk Daireleri).
Site dakikada ~5 belge veriyor; bu sınır aşılmaya çalışılmadı.

Kararlar mevzuattan **ayrı indekste**. Tek indekste birleştirilse maddeleri
sıradan iterler; kullanıcının önce dayanak maddeyi görmesi gerekiyor.

### Ölçülerek bulunan veri hataları

Hepsinin ortak özelliği: **hiçbiri hata mesajı vermiyordu.**

| Sorun | Nasıl anlaşıldı | Çözüm |
|---|---|---|
| iframe HTML uzun kanunları kesiyordu | TMK 1030 madde yerine 425 verdi | PDF birincil kaynak |
| PDF kütüphanesi kelime bölüyordu | 1000 kelimede 12 bozuk token | pypdf → PyMuPDF |
| Aynı numaralı farklı kanunlar çakışıyordu | 104 madde indekse hiç girmemiş | Kimliğe "tertip" eklendi |
| Mülga tespiti yanlıştı | 54 maddenin 20'si yürürlükteydi | Tam/kısmi mülga ayrımı |
| Belge adresi tür bazında değişiyordu | 4.099 belge boş PDF döndürüyordu | Tür → dizin eşlemesi |
| Madde başlığı olmayan belgeler atılıyordu | Tebliğlerin bir kısmı düz metin | Paragraflara bölünüyor |
| Sunucunun bakım sayfası indekslendi | 68 çöp kayıt | Üç sahte PDF boyutu tanınıyor |

Bu düzeltmeler kapsamı **%30'dan %73'e** çıkardı — yeni bir çalışmayla değil,
var olan belgelerin neden alınamadığının bulunmasıyla.

---

## 4. Arama nasıl çalışıyor

**Birinci aşama — aday toplama.** Üç sinyal birleştirilir (RRF):
anlamsal arama (embedding), kelime araması (BM25), doğrudan madde numarası.

**İkinci aşama — yeniden sıralama.** Cross-encoder modeli, ilk aşamanın
bulduğu 50 adayı soruyla birlikte tek tek okuyup yeniden sıralar.

### Ölçülerek yapılan iyileştirmeler

| Değişiklik | Etkisi |
|---|---|
| Yeniden sıralama | %35 → %53 |
| Türkçe yazım düzeltme | %53 → %59 |
| Puan harmanlama | %59 → %71 |
| Gönderilen madde 5 → 10 | cevaba dahil %82 → %91 |
| Vektör aramasının değişmesi | 5,3 sn → 1,5 sn |
| Sıralayıcının gördüğü metin 2 katına | MRR 0,447 → 0,474 |
| **Genişletme için hızlı model** | **76,8 sn → 1,6 sn** |

Sondan ikinci satır: sıralama modeli maddenin ilk 768 karakterini görüyordu;
külliyattaki **58.975 madde (%34) bundan uzun.**

Son satır: sorgu genişletme büyük modelde 76,8 saniye sürüyordu.
`gemini-flash-lite` aynı işi 1,6 saniyede yapıyor — 48 kat fark. Büyük model
"tek kelime yaz" gibi bir isteği bile 36,7 saniyede döndürüyor ve sık sık
503 veriyor.

### Denenip bırakılanlar

| Fikir | Sonuç |
|---|---|
| Ek/geçici madde cezasını artırmak | Üç sette de fark yok |
| Soru kalıplarını atma | 224 soruda 3 soru — gürültü sınırında |

---

## 5. Doğruluk

Üç ayrı soru setiyle ölçüldü:

| Set | Nasıl üretildi | MRR |
|---|---|---|
| El yazımı (34) | elle, cevabı doğrulanarak | 0,710 |
| Yerel model (150) | 3B model üretti, dili çoğu kez bozuk | 0,458 |
| **Gemini (40)** | **doğal Türkçe, günlük dil** | **0,255** |

**Sorular ne kadar doğal yazılırsa isabet o kadar düşüyor.** Aynı bilgiyi
soran üç sorgu:

| Sorgu | Doğru maddenin sırası |
|---|---|
| `kıdem tazminatı şartları` | 1 |
| `kıdem tazminatı` | 8 |
| `kıdem tazminatına hak kazanmak için ne kadar çalışmak gerekir` | 21 |

Sistemin asıl zayıflığı bu. Sorgu genişletme bunu kısmen kapatıyor
(el yazımı sette 0,710 → 0,843) ve hızlı modelle artık uygulanabilir.

---

## 6. Karşılaştırma: Aibars mı, doğrudan yapay zekâ mı

Asıl soru: bu sistemi kurmak yerine doğrudan bir dil modeline sorsak ne
kaybederiz? İki ayrı test yapıldı.

### Test 1 — iş hukuku (52 gerçek avukat sorusu)

Puanlama nesnel: cevapta gösterilen madde külliyatta var mı, konuyla ilgili mi.

| | atıf | gerçekten var | konuyla ilgili | atıfsız |
|---|---|---|---|---|
| çıplak Gemini | 71 | %100 | 64 | **12** |
| Aibars | 106 | %83 | **65** | 10 |
| Claude | 52 | %100 | 50 | 0 |

**Sonuç: başabaş.** İş hukuku dil modelinin en iyi bildiği alan; 4857 sayılı
Kanun internette binlerce kez yazılmış. Orada külliyatın katkısı yok.

Aibars'ın belirgin bir başarısızlığı: kıdem tazminatının temel şartını soran
soruda *"dayanak bulamadım"* dedi. (Sebebi 8. bölümde.)

### Test 2 — bilinmeyen mevzuat (50 soru)

Tebliğ ve kurum yönetmeliklerinden, cevabı somut bir sayı olan sorular.

| | doğru | oran |
|---|---|---|
| çıplak Gemini | 27/47 | **%57** |
| **Aibars** | **43/47** | **%91** |

*(Gemini'nin 3 zaman aşımı ayıklandı.)*

Gemini'nin yanlışları uydurma: doğrusu 3 iken **4**, doğrusu 3 iken **15**,
doğrusu 50 iken **"%40 ve %60"**, doğrusu 17 iken **9**.

### Üçüncü yanıt: Claude

İlk 10 soru Claude'a da soruldu, külliyata bakmadan:

| | Doğru |
|---|---|
| **Claude** | **2/10** |
| çıplak Gemini | 6/10 |
| **Aibars** | **9/10** |

Claude'un doğru bildiği ikisi de tahmindi. Bir soruda emin bir tonla yanlış
cevap verdi (%80 dedi, doğrusu %20).

### Sonuç

| Alan | Değerlendirme |
|---|---|
| Ünlü kanunlar | **Başabaş.** Model zaten biliyor |
| Bilinmeyen mevzuat | **%91'e karşı %57.** Fark gerçek ve ölçülmüş |

Bu, "Aibars daha akıllı" demek değil — cevabı yazan yine Gemini. Fark şu:
Aibars **doğru metni bulup veriyor.** Değer aramada, modelde.

---

## 7. Ölçüm nasıl doğrulandı

Sayılara güvenilebilmesi için ölçüm yönteminin kendisi de denetlendi. Üç
noktada düzeltme gerekti:

| Sorun | Düzeltme |
|---|---|
| Sorular maddelerden otomatik üretilince "hangi kanun bu maddeyi değiştirdi" gibi hukuk sorusu olmayan sorular çıkıyordu | Sorular elle yazıldı; otomatik üretimde yalnızca ölçü birimli somut sayılar hedeflendi |
| Kaynak gösterimini yakalayan desen tek bir yazım biçimini tanıyordu | Üç ayrı biçim desteklendi (`m.53`, `Madde 53`, `53. maddesi`) |
| Alıntılanan madde metninde geçen kanun adları da atıf sayılıyordu | Yalnızca parantez içinde ya da "Dayanak:" başlığı altında gösterilenler sayıldı |

Her düzeltmeden sonra ölçüm baştan çalıştırıldı; rapordaki sayılar son
sürümün sonuçlarıdır.

## 8. Bilinen eksikler ve çözüm yolları

| Eksik | Durum |
|---|---|
| **Doğal dil zayıflığı** (MRR 0,26) | Kısmen çözüldü. Genişletme 0,710 → 0,843 kazandırıyor, hızlı modelle 1,6 saniyeye indi |
| **Temel soruda çuvallama** | Sebebi bulundu: normlar hiyerarşisi zayıf. Kanuna 1,00, kurum yönetmeliğine 0,88 — sadece %12 fark. Kıdem sorusunda BOTAŞ ve TP personel yönetmelikleri kanunun önüne geçiyor. Ölçüm sürüyor |
| **Sessiz bozulmalar** | Çözülebilir: her değişiklikten sonra otomatik duman testi (~30 dk iş) |
| **Versiyon kontrolü yok** | 10 dakikalık iş, henüz yapılmadı |
| **İçtihat sadece iş hukuku** | Her yeni alan ~2 saat indirme |
| **Kapsam %73** | Aranan tebliğ %27 ihtimalle yok ve sistem bunu söyleyemiyor |
| **Hiçbir avukat denemedi** | En büyük eksik |

---

## 9. Şu anki durum

| | |
|---|---|
| Madde | 275.806 |
| Belge | 10.601 (kapsam %73) |
| Mahkeme kararı | 2.890 (iş hukuku) |
| Arama süresi | ~1,8 saniye |
| Test | 132 geçiyor |
| Donanım | RTX 3050, 4 GB |
| Gemini maliyeti | Günde ~0,3 dolar (ağır test dahil) |

### Dürüst değerlendirme

**Mühendislik olarak 7/10.** Ölçülmüş gerçek bir değer var, sessiz hatalar
sistematik olarak bulundu, ölçüm disiplini kuruldu. Ama doğal dil zayıflığı
tam çözülmedi.

**Ürün olarak 3/10.** Çalışıyor ve kaynak gösteriyor, ama hiçbir avukat
denemedi, içtihat tek alanda, kapsam %73 ve sistem eksik olduğunu
söyleyemiyor.

**Kanıtlanan iddia:** *"Bildiğin kanunları sorma, bilmediklerini sor."*
Bilinen mevzuatta dil modeline üstünlük yok; bilinmeyen mevzuatta
%91'e karşı %57.

**Kanıtlanmayan iddia:** genel olarak daha doğru cevap verdiği. Ölçüm bunu
göstermiyor ve gösteren bir ölçüm de yapılmadı.

**En değerli sonraki adım:** bir avukata bir saat kullandırmak. Gerçek
sorunları ancak o gösterir; 500 sentetik sorudan daha çok şey öğretir.
