# mevzuat-rag

Türk mevzuatı üzerinde çalışan, **madde bazlı** yerel bir RAG sistemi. Mevzuat
metinleri `mevzuat.gov.tr`'den çekilir, her madde ayrı bir parça olarak yerel
GPU'da vektöre çevrilir, sorular yalnızca getirilen maddelere dayanarak
cevaplanır.

> Bu araç genel bilgi verir, **hukuki görüş yerine geçmez**. Çıktıyı bir
> avukata danışmadan karar dayanağı yapmayın.

## Ne işe yarıyor

Bilinmeyen mevzuatta (tebliğ, kurum yönetmeliği) çıplak bir dil modeline göre
fark büyük — 50 soruluk sette:

| | doğru |
|---|---|
| çıplak Gemini | %57 |
| **Aibars** | **%91** |

Ünlü kanunlarda (İş K., TBK gibi) fark yok; model zaten biliyor. Değer
modelde değil, doğru maddeyi bulup modele vermekte. Ayrıntı: `AIBARS_TAM_RAPOR.md`.

## Güncel arama isabeti

34 soruluk ölçüm setinde (`tests/olcum_seti.py`):

| Yöntem | 1. sırada | MRR |
|---|---|---|
| Ham hibrit arama | 12/34 | 0,54 |
| + yeniden sıralama, puan harmanlama, HyDE, parent-child | 32/34 | **0,925** |

Doğal, günlük dille sorulan sorularda isabet daha düşük (MRR ~0,26-0,45) —
bu, sistemin en belirgin zayıflığı. `/api/netlestir` olay anlatımını mesele
başlıklarına çevirerek bu farkı kapatmaya çalışıyor (5 olayın 5'inde MRR 1,00).

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

Temel tasarım tercihleri: madde bazlı chunking (sabit karakterle kesmek
yerine), kaynak olarak PDF (site HTML'i uzun kanunları sessizce kesiyor),
PDF çıkarıcı olarak PyMuPDF, iki aşamalı arama (hızlı aday toplama + cross-
encoder ile yeniden sıralama), hibrit arama (madde no + vektör + BM25),
mülga/kısmi mülga ayrımının takibi.

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\pip install -r requirements.txt
```

CUDA'yı doğrulayın:

```bash
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"
```

Ayarlar için `.env.example` dosyasını `.env` olarak kopyalayın.

### Cevap üretimi sağlayıcısı

`.env` içindeki `PROVIDER` değeriyle seçilir:

- `PROVIDER=local` — GGUF model, tamamen çevrimdışı, ücretsiz
  (`Qwen2.5-3B-Instruct-Q4_K_M`, 4 GB VRAM için uygun):

  ```bash
  .venv\Scripts\pip install llama-cpp-python==0.3.4 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
  .venv\Scripts\python -c "from huggingface_hub import hf_hub_download; hf_hub_download('bartowski/Qwen2.5-3B-Instruct-GGUF','Qwen2.5-3B-Instruct-Q4_K_M.gguf',local_dir='models')"
  ```

- `PROVIDER=gemini` — `GEMINI_API_KEY` gerekir. Daha iyi Türkçe sentez ve
  geniş bağlam, ancak **sorulan maddeler Google'a gönderilir**.

Embedding her iki durumda da yerel GPU'da çalışır.

## Kullanım

```bash
python cli.py cek --pilot          # pilot: 6 temel kanun (İş K., TBK, TMK, TCK, HMK, KVKK)
python cli.py katalog --tur 1      # tüm kanunlar (~916 mevzuat)
python cli.py cek
python cli.py indeksle             # GPU
python cli.py sor "yillik ucretli izin suresi kac gundur"
```

Arayüz (**Aibars**):

```bash
.venv\Scripts\python server.py
```

Sonra tarayıcıda `http://localhost:8000`. Sunucu yalnızca `localhost`'ta
dinler, dışarıya bir şey göndermez, anahtar gerektirmez. Streamlit arayüzü
de duruyor (`streamlit run app.py`) ama asıl arayüz Aibars.

Mahkeme kararları ayrı bir indekste tutulur:

```bash
python cli.py ictihat --gecikme 12 --adet 150   # Yargıtay
python cli.py danistay --adet 150               # Danıştay
python cli.py karar-indeksle
```

## Üretilen çıktının doğrulanması

Yerel 3B model önüne konan maddeye rağmen sayı ve kaynak uydurabiliyor. Bu
yüzden cevap üretildikten sonra iki denetimden geçer: **atıf denetimi**
(cevaptaki her `(Kanun m.X)` gösterimi getirilen maddelerle karşılaştırılır)
ve **sayı denetimi** (cevaptaki her rakamın kaynak metinde geçtiği
doğrulanır). Eşleşmeyen varsa cevabın altına `⚠ Doğrulanmalı` uyarısı
eklenir — denetim hatayı önlemez, görünür kılar.

## Testler

```bash
python -m pytest tests/ -q
python olcum.py                    # arama isabeti ölçümü
```

Testler ağ bağlantısı gerektirmez; önbellekteki PDF'leri kullanır, yoksa
atlanır.

## Bilinen sınırlar

- Doğal, günlük dille yazılan sorularda isabet düşüyor (yukarıya bakınız)
- Sorgu genişletme (LLM ile terim zenginleştirme) isabeti artırıyor ama
  yavaş ve dış servise bağımlı olduğu için varsayılan kapalı (`SORGU_GENISLET=1`)
- ASCII (Türkçe karaktersiz) sorgularda isabet kalıcı olarak daha zayıf
- Yerel 3B model cevap kalitesi için yeterli değil; `PROVIDER=gemini` bunu
  büyük ölçüde çözer ama sorulan maddeler Google'a gider
- 9 kanun ayrıştırılamadı — 1920'ler Osmanlıca metinler, farklı madde biçimi
- Tebliğ ve yönetmelikler henüz tam olarak yeniden ayrıştırılmadı

## Veri kaynağı ve kullanım

Veriler `mevzuat.gov.tr`'den, kimlik doğrulama gerektirmeyen açık uçlardan
alınır. İstekler arasında 1.5 saniye beklenir, `User-Agent` içinde iletişim
bilgisi taşınır, indirilen her belge yerel önbelleğe alınır.

Kanun, yönetmelik ve yargı kararları FSEK m.31 uyarınca telif korumasına
tabi değildir.

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
| `core/hyde.py` | HyDE: varsayımsal hüküm ile arama |
| `core/cocuk.py` | Parent-child: uzun madde kuyruğu için çocuk vektör |
| `core/yazim.py` | Aksansız sorguları külliyattan çıkarılan sözlükle düzeltme |
| `core/sorgu.py` | Sorgu genişletme (varsayılan kapalı) |
| `core/generate.py` | Sağlayıcı seçmeli cevap üretimi |
| `olcum.py` | Arama isabeti ölçümü |
| `tests/olcum_seti.py` | 34 soruluk ölçüm seti (cevaplarıyla) |
| `cli.py` | `katalog` / `cek` / `indeksle` / `sor` / `ictihat` / `danistay` |
| `server.py` | Aibars web sunucusu (yalnızca localhost) |
| `web/aibars.html` | Aibars arayüzü |
| `app.py` | Streamlit arayüzü (alternatif) |
