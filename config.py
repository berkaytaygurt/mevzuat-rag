"""Proje geneli ayarlar. .env varsa oradan okur, yoksa makul varsayilanlar."""
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
INDEX_DIR = ROOT / "data" / "index"
CERT_BUNDLE = ROOT / "certs" / "mevzuat-ca-bundle.pem"

for d in (RAW_DIR, INDEX_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- scraper ---
BASE_URL = "https://www.mevzuat.gov.tr"
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.5"))
SCRAPE_CONTACT = os.getenv("SCRAPE_CONTACT", "")
USER_AGENT = (
    f"mevzuat-rag/0.1 (kisisel arastirma projesi"
    + (f"; iletisim: {SCRAPE_CONTACT}" if SCRAPE_CONTACT else "")
    + ")"
)

# --- embedding ---
EMBED_MODEL = os.getenv("EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cuda")
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "8"))
EMBED_MAX_SEQ = int(os.getenv("EMBED_MAX_SEQ", "512"))

# --- yeniden siralama (cross-encoder) ---
RERANK = os.getenv("RERANK", "1") not in ("0", "false", "hayir")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_BATCH = int(os.getenv("RERANK_BATCH", "6"))
# Cross-encoder maddenin ilk max_seq token'ini goruyor. 256 token
# (~768 karakter) kulliyattaki 58.975 maddeyi (%34) kesiyordu.
# Olculdu (150 soruluk sette, tek yonlu artis):
#     256 -> MRR 0.447, ilk-5 85
#     384 -> MRR 0.457, ilk-5 85
#     512 -> MRR 0.474, ilk-5 89
# Bedeli sorgu basina 1.21 sn yerine 1.45 sn. Yigin 12'den 6'ya
# dusuruldu: 4 GB VRAM'de uzun dizi ile 12'lik yigin sigmiyor.
RERANK_MAX_SEQ = int(os.getenv("RERANK_MAX_SEQ", "512"))
# Ilk asamadan kac aday alinip yeniden siralanacak.
# Olculen en iyi nokta 25. Genisletmek tavani yukseltiyor (12 adayda ilk
# asama dogru maddeyi %88, 50 adayda %97 oranda havuza sokuyor) ama cikti
# degismiyor: darbogaz aday havuzu degil, siralayicinin karari. 50 ile 25
# ayni sonucu veriyor, 25 daha hizli.
RERANK_ADAY = int(os.getenv("RERANK_ADAY", "25"))
# Cross-encoder girdilerinde Turkce harfleri ASCII'ye katla
RERANK_KATLA = os.getenv("RERANK_KATLA", "1") not in ("0", "false", "hayir")
# Nihai siralamada cross-encoder puaninin agirligi (kalani ilk asamanin RRF'i).
# 1.0 = yalnizca cross-encoder, 0.0 = yalnizca ilk asama.
RERANK_AGIRLIK = float(os.getenv("RERANK_AGIRLIK", "0.9"))
# Ek/Gecici maddelere verilen kucuk siralama cezasi (0 = kapali)
EK_MADDE_CEZASI = float(os.getenv("EK_MADDE_CEZASI", "0.05"))
# Normlar hiyerarsisine gore siralama (kanun > yonetmelik > teblig)
HIYERARSI = os.getenv("HIYERARSI", "1") not in ("0", "false", "hayir")

# --- yazim duzeltme ---
# Aksansiz yazilan sorguyu kulliyattan cikarilan sozlukle gercek yazimina cevirir
YAZIM_DUZELT = os.getenv("YAZIM_DUZELT", "1") not in ("0", "false", "hayir")

# --- sorgu genisletme ---
# Sorguyu aramadan once LLM'e verip hukuk terimleriyle zenginlestirir.
# Her aramaya bir LLM cagrisi ekler; varsayilan kapali.
SORGU_GENISLET = os.getenv("SORGU_GENISLET", "0") not in ("0", "false", "hayir")
# Genisletmeyi hangi model yapsin. Cevap ureticisinden ayri tutuluyor: bu is
# basit (8 terim uretmek) ve gecikmeye cok duyarli, cevap uretimi ise degil.
GENISLET_PROVIDER = os.getenv("GENISLET_PROVIDER", os.getenv("PROVIDER", "local")).lower()
# Uyarlamali genisletme esigi: en iyi adayin cross-encoder puani bunun
# altindaysa sorgu genisletilip tekrar aranir. Yuksek esik = daha cok
# genisletme = daha yavas ama daha isabetli.
GENISLET_ESIK = float(os.getenv("GENISLET_ESIK", "0.5"))

# --- generation ---
PROVIDER = os.getenv("PROVIDER", "local").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Olculdu: buyuk model ayni istegi 36.7 saniyede donduruyor ve sik sik 503
# veriyor; flash-lite 0.9 saniyede ve dogru cevapliyor. Bu isin (verilen
# maddeyi okuyup ozetlemek) buyuk modele ihtiyaci yok.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
# Birincil model mesgulse (503) sirayla denenir
# Cevap uretimi icin toplam sure butcesi (saniye). Asilirsa hizli hata
# verilir; tunel zaten 100 saniyede kopuyor.
GEMINI_SURE_BUTCESI = float(os.getenv("GEMINI_SURE_BUTCESI", "45"))
GEMINI_YEDEK_MODELLER = [
    m.strip() for m in os.getenv(
        "GEMINI_YEDEK_MODELLER", "gemini-3.5-flash,gemini-3.7-flash,gemini-flash-latest"
    ).split(",") if m.strip()
]
LOCAL_MODEL_PATH = os.getenv("LOCAL_MODEL_PATH", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
# 3B model tamamen GPU'ya alindiginda (=-1) 4 GB kartta arama modelleriyle
# cakisiyor. Windows hata vermiyor, sessizce sistem bellegine tasiyor ve
# arama 1.5 saniye yerine 67 saniye suruyordu. Olculdu: temiz kartta 3.46 GB
# bos var; embedding 1.2 + siralayici 1.1 + 3B model 2.0 = 4.3 GB.
# Cevap uretimi islemcide yavas ama arama hizli kaliyor -- dogru takas bu,
# cunku her sorgu arama yapiyor, cevap ise istege bagli.
LOCAL_GPU_LAYERS = int(os.getenv("LOCAL_GPU_LAYERS", "0"))
LOCAL_CTX = int(os.getenv("LOCAL_CTX", "8192"))

# mevzuat.gov.tr tur kodlari (MevzuatTur parametresi)
MEVZUAT_TURLERI = {
    1: "Kanun",
    2: "Cumhurbaskanligi Kararnamesi",
    3: "Kanun Hukmunde Kararname",
    4: "Tuzuk",
    7: "Cumhurbaskanligi Yonetmeligi",
    8: "Kurum ve Kurulus Yonetmeligi",
    9: "Teblig",
    21: "Yonetmelik",
}


# --- sunucu ---
# Varsayilan olarak yalnizca kendi makinende dinler. Baskasinin erisebilmesi
# icin HOST=0.0.0.0 yapilir; o durumda sifre zorunludur (bkz. server.py).
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
KULLANICI = os.getenv("AIBARS_KULLANICI", "")
SIFRE = os.getenv("AIBARS_SIFRE", "")

# Mahkeme kararlari cevaba ayri bir bolum olarak eklensin mi. Kapatildiginda
# kararlar yalnizca arayuzde listelenir, uretilen cevaba girmez -- yerel
# modelin baglam penceresi dar oldugu icin bu bazen mevzuat cevabini
# zayiflatiyor.
KARARLARI_CEVABA_KAT = os.getenv("KARARLARI_CEVABA_KAT", "1") == "1"

# Sorgunun soru kaliplarindan arindirilmis halini de ayri bir sinyal olarak
# aramak. Olculen sorun: "kidem tazminati sartlari" dogru maddeyi 1. sirada
# getiriyor, ayni seyi soran dogal cumle 21. siraya dusuruyor.
CEKIRDEK_SORGU = os.getenv("CEKIRDEK_SORGU", "1") not in ("0", "false", "hayir")
CEKIRDEK_AGIRLIK = float(os.getenv("CEKIRDEK_AGIRLIK", "1.0"))

# Gemini icin gunluk sert istek tavani. Google'in butce uyarisi harcamayi
# durdurmaz, yalnizca haber verir; bu sayac durdurur. Sayac diske yaziliyor,
# surec yeniden baslasa da gunluk toplam korunuyor.
GEMINI_GUNLUK_SINIR = int(os.getenv("GEMINI_GUNLUK_SINIR", "1500"))

# Genisletme uyarlamali calisir: yalnizca ilk arama zayif sonuc verdiginde
# tetiklenir. Olculdu -- 448 sorgunun yalnizca 28'inde (%6) devreye girdi,
# yani fikir test bile edilmemis oldu. Bu bayrak esigi atlayip her sorguda
# genisletir; fikrin gercek etkisini olcmek icin.
GENISLET_HEP = os.getenv("GENISLET_HEP", "0") not in ("0", "false", "hayir")

# Sorgu genisletme gibi KUCUK isler icin ayri, hizli model. Olculdu --
# ayni onemsiz istek ("tek kelime yaz") su surelerde donuyor:
#     gemini-3.6-flash          36.7 sn  (ve sik sik 503)
#     gemini-flash-lite-latest   0.6 sn
# Genisletme kisa bir terim listesi uretiyor; buyuk model gereksiz.
GEMINI_HIZLI_MODEL = os.getenv("GEMINI_HIZLI_MODEL", "gemini-flash-lite-latest")
