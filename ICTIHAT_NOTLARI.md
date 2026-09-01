# İçtihat entegrasyonu — araştırma notları

Bu iş yarım kaldı. Bulunanlar ve tıkanılan nokta aşağıda.

## Çözülenler

**İki site de aynı altyapıyı kullanıyor** (Adalet Bakanlığı):
`emsal.uyap.gov.tr` ve `karararama.yargitay.gov.tr`

| Uç | İş |
|---|---|
| `POST /aramadetaylist` | Arama sonuç listesi (id, daire, esas/karar no, tarih) |
| `GET /getDokuman?id=` | Kararın tam metni (JSON içinde HTML) |

**Gövde şekli:** `{"data": { ...tüm form alanları... }}`
Alanların tamamı gönderilmeli; eksik alan `ADALET_RUNTIME_EXCEPTION` döndürüyor.

**Yargıtay'da daire filtresi var** (UYAP'ta yok):
- `birimYrgHukukDaire` — Hukuk Daireleri, çoklu seçim `+` ile birleştirilir
- `birimYrgCezaDaire`, `birimYrgKurulDaire`

İş hukuku için `"9. Hukuk Dairesi+22. Hukuk Dairesi"` kullanılmalı. Bu, kelime
aramasından çok daha güvenilir bir alan filtresi olur.

**Karar metninin yapısı:**
- Başlık bloğu (mahkeme, dosya no, taraflar) — anonimleştirilmiş, değersiz
- `GEREĞİ DÜŞÜNÜLDÜ` / `GEREĞİ GÖRÜŞÜLDÜ` — buradan sonrası esas kısım, ancak
  önce **tarafların iddiaları** gelir, mahkemenin görüşü değil
- `DELİLLERİN DEĞERLENDİRİLMESİ VE GEREKÇE:` — **mahkemenin kendi gerekçesi**,
  aranan asıl bilgi burada
- `HÜKÜM` / `SONUÇ` — karar

İlk denemede `GEREĞİ DÜŞÜNÜLDÜ`'yü işaret aldım, yanlıştı: taraf iddialarını da
kapsıyor.

## Tıkanılan noktalar

**1. Arama parametresi içeriği filtrelemiyor.**
UYAP'ta `kıdem tazminatı` arayıp indirilen 11 kararın hiçbirinde bu ifade
geçmiyordu; gelen kararlar araç kiralama, ticari alacak gibi alakasız
konulardı. `recordsTotal` kelimeye göre değişiyor, yani bir şey filtreliyor —
ama sonuç metinleriyle örtüşmüyor. Hangi alana baktığı çözülemedi.

**2. WAF.** Çerezlerde `TS01f02b04` var (F5 BIG-IP ASM). Çok sayıda istekten
sonra her iki site de `ADALET_RUNTIME_EXCEPTION` döndürmeye başladı.
CAPTCHA şu an kapalı (`isDisplayCaptcha: false`), engel o değil.

## Sonraki adım önerisi

Tahmin etmeyi bırakıp **gerçek tarayıcıda bir arama yapıp ağ isteğini
gözlemlemek.** Sitenin kendi gönderdiği gövde görülürse hangi alanın içerik
araması yaptığı kesin olarak anlaşılır. Tarayıcı araçlarıyla mümkün.

Ayrıca istek hızı baştan çok daha yavaş tutulmalı (5-10 sn), WAF'ı tetiklememek
için.

## Yazılmış kod

- `scraper/ictihat.py` — arama + belge çekme, tekrar denemeli, önbellekli
- `scraper/karar_parser.py` — gerekçe ayıklama (işaret düzeltilmeli)
- `cli.py ictihat` — toplu indirme komutu

Hiçbiri ana sisteme bağlı değil; kanun tarafı bunlardan etkilenmiyor.
